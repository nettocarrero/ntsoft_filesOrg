from pathlib import Path

from app.config import load_settings
from app.models import DocumentInfo, DocumentType
from app.services.classifier_service import classify_document
from app.services.cnpj_service import build_cnpj_index
from app.utils import normalize_text


def test_normalize_text_basic():
    assert normalize_text("São Benedito - CE") == "sao benedito ce"


def test_classification_by_alias_in_filename(tmp_path):
    settings = load_settings()
    fake_pdf = tmp_path / "boleto_ubajara_teste.pdf"
    fake_pdf.write_text("dummy", encoding="utf-8")

    doc = DocumentInfo(original_path=fake_pdf)
    doc.text = "boleto de aluguel"
    doc.text_status = "ok"

    classified = classify_document(doc, settings)

    assert classified.suggested_store == "ljUbj"
    assert classified.store_confidence > 0


def test_store_found_only_in_folder(tmp_path):
    settings = load_settings()
    folder = tmp_path / "ubajara"  # evidência apenas na pasta
    folder.mkdir()
    pdf_path = folder / "documento.pdf"
    pdf_path.write_text("conteudo generico", encoding="utf-8")

    doc = DocumentInfo(original_path=pdf_path)
    doc.text = "conteudo generico"
    doc.text_status = "ok"

    classified = classify_document(doc, settings)

    assert classified.suggested_store == "ljUbj"
    assert "folder" in classified.score_details["matched_store_sources"]


def test_store_found_only_in_text(tmp_path):
    settings = load_settings()
    pdf_path = tmp_path / "documento.pdf"
    pdf_path.write_text("dummy", encoding="utf-8")

    doc = DocumentInfo(original_path=pdf_path)
    doc.text = "Documento referente a loja de Guaraciaba do Norte."
    doc.text_status = "ok"

    classified = classify_document(doc, settings)

    assert classified.suggested_store == "ljGba"
    assert "text" in classified.score_details["matched_store_sources"]


def test_tie_between_stores_goes_to_review(tmp_path):
    settings = load_settings()
    pdf_path = tmp_path / "ubajara_ibiapina.pdf"
    pdf_path.write_text("dummy", encoding="utf-8")

    # Texto neutro para forçar empate baseado no nome
    doc = DocumentInfo(original_path=pdf_path)
    doc.text = "documento neutro"
    doc.text_status = "ok"

    classified = classify_document(doc, settings)

    # Pode não haver loja sugerida ou, se houver, deve ir para revisão
    if classified.suggested_store is None:
        assert classified.sent_to_review is True
    else:
        assert classified.sent_to_review is True


def test_unknown_document_type(tmp_path):
    settings = load_settings()
    pdf_path = tmp_path / "sem_tipo_claro.pdf"
    pdf_path.write_text("dummy", encoding="utf-8")

    doc = DocumentInfo(original_path=pdf_path)
    doc.text = "Texto sem nenhuma palavra chave clara para classificação."
    doc.text_status = "ok"

    classified = classify_document(doc, settings)

    assert classified.suggested_doc_type == DocumentType.DESCONHECIDO
    assert classified.type_confidence == 0.0 or classified.type_confidence < 0.2


def test_boleto_with_strong_text_signals_is_classified_as_boleto(tmp_path):
    settings = load_settings()
    pdf_path = tmp_path / "boleto_teste.pdf"
    pdf_path.write_text("dummy", encoding="utf-8")

    text = """
    Boleto Bancário
    Recibo do Pagador
    Beneficiário: Banco Bradesco
    Pagador: VAREJAO CHOCOBALAS COMERCIAL DE ALIMENTOS LTDA
    Nosso número: 123456789
    Agência / Código do Beneficiário: 1234/56789
    Vencimento: 10/03/2026
    Valor do documento: 1.871,00
    Linha Digitavel: 23790.75209 90000.000118 82000.694503 1 13810000187100
    """

    doc = DocumentInfo(original_path=pdf_path)
    doc.text = text
    doc.text_status = "ok"

    classified = classify_document(doc, settings)

    assert classified.suggested_doc_type == DocumentType.BOLETO


def test_sent_to_review_when_no_store(tmp_path):
    settings = load_settings()
    pdf_path = tmp_path / "documento_generico.pdf"
    pdf_path.write_text("dummy", encoding="utf-8")

    doc = DocumentInfo(original_path=pdf_path)
    doc.text = "Documento sem referência de loja ou tipo."
    doc.text_status = "ok"

    classified = classify_document(doc, settings)

    assert classified.suggested_store is None or classified.store_confidence < 0.5
    assert classified.sent_to_review is True


def test_document_with_only_cnpj_is_auto_classified(tmp_path):
    settings = load_settings()
    aliases = settings.aliases
    cnpj_index = build_cnpj_index(aliases)
    # escolhe um CNPJ conhecido
    some_cnpj, store_code = next(iter(cnpj_index.items()))

    pdf_path = tmp_path / "somente_cnpj.pdf"
    pdf_path.write_text("dummy", encoding="utf-8")

    doc = DocumentInfo(original_path=pdf_path)
    doc.text = f"Pagamento referente à loja. CNPJ: {some_cnpj}"
    doc.text_status = "ok"

    classified = classify_document(doc, settings)

    assert classified.suggested_store == store_code
    assert classified.sent_to_review is False
    assert classified.has_strong_store_evidence is True
    assert classified.strong_evidence_type == "cnpj_match"
    assert classified.store_confidence >= 0.95


def test_document_with_cnpj_and_low_noise_from_other_store(tmp_path):
    settings = load_settings()
    aliases = settings.aliases
    cnpj_index = build_cnpj_index(aliases)
    some_cnpj, store_code = next(iter(cnpj_index.items()))

    pdf_path = tmp_path / "cnpj_com_ruido.pdf"
    pdf_path.write_text("dummy", encoding="utf-8")

    # adiciona um nome de outra cidade no texto para gerar ruído
    doc = DocumentInfo(original_path=pdf_path)
    doc.text = f"CNPJ {some_cnpj} boleto referente. Cidade citada: Guaraciaba."
    doc.text_status = "ok"

    classified = classify_document(doc, settings)

    assert classified.suggested_store == store_code
    assert classified.sent_to_review is False
    assert classified.has_strong_store_evidence is True


def test_document_without_cnpj_and_single_weak_evidence_still_review(tmp_path):
    settings = load_settings()
    pdf_path = tmp_path / "evidencia_unica_fraca.pdf"
    pdf_path.write_text("dummy", encoding="utf-8")

    # apenas uma menção fraca no texto, sem CNPJ
    doc = DocumentInfo(original_path=pdf_path)
    doc.text = "Talvez relacionado a ubajara."
    doc.text_status = "ok"

    classified = classify_document(doc, settings)

    assert not classified.detected_cnpjs
    assert classified.sent_to_review is True


def test_document_with_conflicting_cnpjs_goes_to_review(tmp_path):
    settings = load_settings()
    aliases = settings.aliases
    cnpj_index = build_cnpj_index(aliases)
    # garantir pelo menos dois CNPJs de lojas diferentes
    items = list(cnpj_index.items())
    if len(items) < 2:
        return  # configuração não suporta este teste
    (cnpj1, store1), (cnpj2, store2) = items[0], items[1]

    pdf_path = tmp_path / "cnpjs_conflitantes.pdf"
    pdf_path.write_text("dummy", encoding="utf-8")

    doc = DocumentInfo(original_path=pdf_path)
    doc.text = f"CNPJ {cnpj1} e também CNPJ {cnpj2} aparecem neste documento."
    doc.text_status = "ok"

    classified = classify_document(doc, settings)

    # Deve ir para revisão por conflito de CNPJ
    assert classified.sent_to_review is True

