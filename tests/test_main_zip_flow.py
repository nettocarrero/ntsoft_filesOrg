from pathlib import Path
import zipfile

from app.config import load_settings
from app.main import _process_zip
from app.models.enums import ProcessingStatus


def test_process_zip_pipeline(tmp_path):
    settings = load_settings()

    # cria um ZIP com subpastas e PDFs
    inner_dir = tmp_path / "inner"
    inner_dir.mkdir()
    pdf1 = inner_dir / "doc1.pdf"
    pdf2 = inner_dir / "doc2.PDF"
    pdf1.write_text("conteudo 1", encoding="utf-8")
    pdf2.write_text("conteudo 2", encoding="utf-8")

    zip_path = tmp_path / "entrada.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(pdf1, arcname="loja/ubajara/doc1.pdf")
        zf.write(pdf2, arcname="loja/ubajara/sub/doc2.PDF")

    results = _process_zip(zip_path, settings)

    # Deve haver um resultado por PDF
    assert len(results) == 2
    for r in results:
        assert r.status in {ProcessingStatus.SUCCESS, ProcessingStatus.ERROR}
        assert r.document.came_from_zip is True
        assert r.document.came_from_archive is True
        assert r.document.archive_type == "zip"
        assert r.document.archive_root == zip_path
        assert r.document.extracted_path is not None

