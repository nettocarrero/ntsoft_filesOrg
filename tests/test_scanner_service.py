from pathlib import Path

from app.services.scanner_service import scan_input_files
from app.utils.file_utils import is_pdf, is_zip, is_rar


def test_is_pdf_and_is_zip_case_insensitive(tmp_path):
    pdf_lower = tmp_path / "doc.pdf"
    pdf_upper = tmp_path / "doc.PDF"
    zip_lower = tmp_path / "arq.zip"
    zip_upper = tmp_path / "arq.ZIP"
    rar_lower = tmp_path / "arq.rar"
    rar_upper = tmp_path / "arq.RAR"

    for p in [pdf_lower, pdf_upper, zip_lower, zip_upper, rar_lower, rar_upper]:
        p.write_text("dummy", encoding="utf-8")

    assert is_pdf(pdf_lower) is True
    assert is_pdf(pdf_upper) is True
    assert is_zip(zip_lower) is True
    assert is_zip(zip_upper) is True
    assert is_rar(rar_lower) is True
    assert is_rar(rar_upper) is True


def test_scan_input_files_detects_pdf_zip_and_rar(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()

    pdf_file = input_dir / "file1.pdf"
    zip_file = input_dir / "file2.zip"
    rar_file = input_dir / "file3.rar"
    other_file = input_dir / "ignore.txt"

    pdf_file.write_text("dummy", encoding="utf-8")
    zip_file.write_text("dummy", encoding="utf-8")
    rar_file.write_text("dummy", encoding="utf-8")
    other_file.write_text("dummy", encoding="utf-8")

    files = scan_input_files(input_dir)
    names = {f.name for f in files}

    assert "file1.pdf" in names
    assert "file2.zip" in names
    assert "file3.rar" in names
    assert "ignore.txt" not in names

