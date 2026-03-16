"""Testes para extração de informações financeiras (vencimento e valor)."""
import pytest
from pathlib import Path

from app.services.document_finance_parser import (
    extract_payment_info,
    read_payment_meta_file,
    write_payment_meta_file,
    detect_boleto_signals,
)


def test_extract_payment_info_due_date_and_amount():
    text = """
    Boleto Bancário
    Vencimento: 20/03/2026
    Valor total: R$ 1.234,56
    """
    info = extract_payment_info(text)
    assert info["due_date"] == "2026-03-20"
    assert info["amount"] == 1234.56
    assert info["confidence"] in ("high", "medium", "low")


def test_extract_payment_info_due_date_only():
    text = "Data de vencimento 15-01-2026. Outros dados."
    info = extract_payment_info(text)
    assert info["due_date"] == "2026-01-15"
    assert info["amount"] is None


def test_extract_payment_info_amount_only():
    text = "Valor do documento: 500,00 reais."
    info = extract_payment_info(text)
    assert info["due_date"] is None
    assert info["amount"] == 500.0


def test_extract_payment_info_empty():
    info = extract_payment_info("")
    assert info["due_date"] is None
    assert info["amount"] is None
    assert info["confidence"] == "low"
    assert info["is_boleto"] is False


def test_extract_payment_info_multiple_dates_prioritizes_near_keyword():
    text = """
    Emitido em 01/01/2025. Referência 01/02/2025.
    Vencimento: 20/03/2026. Valor R$ 100,00.
    """
    info = extract_payment_info(text)
    assert info["due_date"] == "2026-03-20"
    assert info["amount"] == 100.0


def test_detect_boleto_by_keywords_and_bank():
    text = """
    Recibo do pagador
    Beneficiário: Banco do Brasil
    Pagador: Empresa XYZ
    Nosso número: 123456789
    Vencimento: 10/03/2026
    Valor do documento: 1.871,00
    """
    info = extract_payment_info(text)
    assert info["is_boleto"] is True
    assert info["boleto_score"] >= 4


def test_detect_boleto_by_linha_digitavel_only():
    text = "23790.75209 90000.000118 82000.694503 1 13810000187100"
    info = extract_payment_info(text)
    assert info["is_boleto"] is True
    assert info["has_linha_digitavel"] is True
    assert info["boleto_score"] >= 5


def test_write_and_read_payment_meta_file(tmp_path):
    pdf_path = tmp_path / "boleto.pdf"
    pdf_path.touch()
    write_payment_meta_file(pdf_path, due_date="2026-03-20", amount=1234.56, extracted=True)
    meta = read_payment_meta_file(pdf_path)
    assert meta is not None
    assert meta["type"] == "pagamento"
    assert meta["due_date"] == "2026-03-20"
    assert meta["amount"] == 1234.56
    assert meta["extracted"] is True


def test_write_and_read_payment_meta_file_not_extracted(tmp_path):
    pdf_path = tmp_path / "doc.pdf"
    pdf_path.touch()
    write_payment_meta_file(pdf_path, due_date=None, amount=None, extracted=False)
    meta = read_payment_meta_file(pdf_path)
    assert meta is not None
    assert meta["due_date"] is None
    assert meta["amount"] is None
    assert meta["extracted"] is False


def test_read_payment_meta_file_missing_returns_none(tmp_path):
    pdf_path = tmp_path / "nometa.pdf"
    pdf_path.touch()
    assert read_payment_meta_file(pdf_path) is None
