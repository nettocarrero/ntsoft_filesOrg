from pathlib import Path
from unittest import mock

from app.config import load_settings
from app.main import _process_pdf
from app.models.enums import ProcessingStatus


def test_pdf_with_sufficient_text_does_not_call_ocr(tmp_path):
    settings = load_settings()
    pdf_path = tmp_path / "suficiente.pdf"
    pdf_path.write_text("dummy", encoding="utf-8")

    with mock.patch("app.main.extract_pdf_text") as mock_extract_text, mock.patch(
        "app.main.extract_text_with_ocr"
    ) as mock_ocr:
        mock_extract_text.return_value = ("texto suficiente para evitar OCR", "ok")
        result = _process_pdf(
            pdf_path,
            settings,
            came_from_archive=False,
            archive_type=None,
        )

    assert result.status in {ProcessingStatus.SUCCESS, ProcessingStatus.ERROR}
    assert result.document.text_source == "pdf_text"
    mock_ocr.assert_not_called()


def test_pdf_with_insufficient_text_triggers_ocr(tmp_path):
    settings = load_settings()
    pdf_path = tmp_path / "insuficiente.pdf"
    pdf_path.write_text("dummy", encoding="utf-8")

    with mock.patch("app.main.extract_pdf_text") as mock_extract_text, mock.patch(
        "app.main.extract_text_with_ocr"
    ) as mock_ocr:
        mock_extract_text.return_value = ("", "texto_insuficiente")
        mock_ocr.return_value = ("texto via ocr", {"pages_processed": 1, "ocr_engine": "tesseract", "text_length": 12, "success": True})

        result = _process_pdf(
            pdf_path,
            settings,
            came_from_archive=False,
            archive_type=None,
        )

    assert result.document.ocr_used is True
    assert result.document.ocr_success is True
    assert result.document.text_source == "ocr"
    assert "ocr_engine" in result.document.ocr_metadata


def test_ocr_failure_does_not_break_pipeline(tmp_path):
    settings = load_settings()
    pdf_path = tmp_path / "falha_ocr.pdf"
    pdf_path.write_text("dummy", encoding="utf-8")

    with mock.patch("app.main.extract_pdf_text") as mock_extract_text, mock.patch(
        "app.main.extract_text_with_ocr"
    ) as mock_ocr:
        mock_extract_text.return_value = ("", "texto_insuficiente")
        mock_ocr.return_value = ("", {"pages_processed": 1, "ocr_engine": "tesseract", "text_length": 0, "success": False})

        result = _process_pdf(
            pdf_path,
            settings,
            came_from_archive=False,
            archive_type=None,
        )

    assert result.status in {ProcessingStatus.SUCCESS, ProcessingStatus.ERROR}
    assert result.document.ocr_used is True
    assert result.document.ocr_success is False

