from pathlib import Path

import fitz  # PyMuPDF

from app.services.pdf_service import extract_pdf_text


def _create_simple_pdf(path: Path, text: str) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    doc.save(path)
    doc.close()


def test_extract_pdf_text(tmp_path):
    pdf_path = tmp_path / "simple.pdf"
    _create_simple_pdf(pdf_path, "Nota fiscal de serviço - São Benedito")

    text, status = extract_pdf_text(pdf_path)

    assert "Nota fiscal" in text or "Nota fiscal".lower() in text.lower()
    assert status in {"ok", "texto_insuficiente"}

