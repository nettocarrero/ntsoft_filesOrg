from pathlib import Path

from app.config import load_settings
from app.models import DocumentInfo
from app.services.filter_service import should_ignore_document


def build_doc(path_name: str, text: str | None = None) -> DocumentInfo:
    return DocumentInfo(original_path=Path(path_name), text=text or "", text_status="ok")


def test_ignore_by_filename_formulario():
    settings = load_settings()
    doc = build_doc("FORMULARIO_CAIXA_123.pdf")
    ignore, reason = should_ignore_document(doc, settings)
    assert ignore is True
    assert "formulario" in reason.lower()


def test_ignore_by_filename_baixa_estoque():
    settings = load_settings()
    doc = build_doc("baixa de estoque - loja.pdf")
    ignore, _ = should_ignore_document(doc, settings)
    assert ignore is True


def test_ignore_by_text_status_pedido_processado():
    settings = load_settings()
    doc = build_doc("qualquer.pdf", text="... Status do Pedido: Processado ...")
    ignore, _ = should_ignore_document(doc, settings)
    assert ignore is True


def test_do_not_ignore_unrelated_document():
    settings = load_settings()
    doc = build_doc("nota_fiscal_123.pdf", text="Nota fiscal de venda")
    ignore, _ = should_ignore_document(doc, settings)
    assert ignore is False


def test_ignore_by_text_generic_rule_even_if_filename_generic():
    settings = load_settings()
    doc = build_doc("qualquer_nome.pdf", text="Este eh um formulario interno da empresa.")
    ignore, reason = should_ignore_document(doc, settings)
    assert ignore is True

