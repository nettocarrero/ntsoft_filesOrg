from pathlib import Path
import zipfile

from app.services.zip_service import extract_zip
from app.config import PathsConfig


def test_extract_zip(tmp_path):
    # cria um zip de teste
    inner_dir = tmp_path / "data"
    inner_dir.mkdir()
    file_inside = inner_dir / "doc.pdf"
    file_inside.write_text("dummy", encoding="utf-8")

    zip_path = tmp_path / "test.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(file_inside, arcname="loja/ubajara/doc.pdf")

    paths = PathsConfig(temp_dir=tmp_path / "temp")
    extracted_files = extract_zip(zip_path, paths.temp_dir)

    assert any(f.name == "doc.pdf" for f in extracted_files)

