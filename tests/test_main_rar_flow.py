from pathlib import Path
from unittest import mock

from app.config import load_settings
from app.main import _process_rar
from app.models.enums import ProcessingStatus


def test_process_rar_pipeline_with_mocked_extraction(tmp_path):
    settings = load_settings()

    rar_path = tmp_path / "entrada.rar"
    rar_path.write_text("dummy", encoding="utf-8")

    # cria PDFs "extraídos" simulados
    extracted_pdf1 = tmp_path / "temp" / "doc1.pdf"
    extracted_pdf2 = tmp_path / "temp" / "sub" / "doc2.PDF"
    extracted_pdf1.parent.mkdir(parents=True, exist_ok=True)
    extracted_pdf2.parent.mkdir(parents=True, exist_ok=True)
    extracted_pdf1.write_text("conteudo 1", encoding="utf-8")
    extracted_pdf2.write_text("conteudo 2", encoding="utf-8")

    with mock.patch("app.main.extract_rar") as mock_extract_rar:
        mock_extract_rar.return_value = [extracted_pdf1, extracted_pdf2]

        results = _process_rar(rar_path, settings)

    assert len(results) == 2
    for r in results:
        assert r.status in {ProcessingStatus.SUCCESS, ProcessingStatus.ERROR}
        assert r.document.came_from_archive is True
        assert r.document.archive_type == "rar"
        assert r.document.archive_root == rar_path
        assert r.document.extracted_path is not None

