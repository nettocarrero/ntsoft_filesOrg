from pathlib import Path

from app.config import WhatsAppIngestionConfig, Settings, PathsConfig, ConfidenceThresholds, ScoringConfig
from app.services.whatsapp_ingestion_service import _generate_safe_destination, _is_supported_extension, WhatsAppIngestionHandler


class DummySettings(Settings):
    pass


def build_dummy_settings(tmp_path: Path) -> Settings:
    paths = PathsConfig(
        input_dir=tmp_path / "input",
        output_dir=tmp_path / "output",
        temp_dir=tmp_path / "temp",
        review_manual_dir=tmp_path / "review",
        reports_dir=tmp_path / "reports",
        data_dir=tmp_path / "data",
    )
    ocr = None  # não usado aqui
    scoring = ScoringConfig(store_weights={})
    wa_cfg = WhatsAppIngestionConfig()
    return Settings(
        paths=paths,
        thresholds=ConfidenceThresholds(),
        scoring=scoring,
        aliases={},
        document_keywords={},
        processed_input=None,  # type: ignore
        ocr=ocr,  # type: ignore
        whatsapp_ingestion=wa_cfg,
    )


def test_generate_safe_destination_creates_unique_names(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    existing = input_dir / "arquivo.pdf"
    existing.write_text("a", encoding="utf-8")

    dest1 = _generate_safe_destination(input_dir, "arquivo.pdf")
    assert dest1.name == "arquivo (1).pdf"
    dest1.write_text("b", encoding="utf-8")
    dest2 = _generate_safe_destination(input_dir, "arquivo.pdf")
    assert dest2.name == "arquivo (2).pdf"


def test_is_supported_extension_filters_correctly(tmp_path):
    settings = build_dummy_settings(tmp_path)
    pdf = tmp_path / "a.pdf"
    rar = tmp_path / "b.RAR"
    txt = tmp_path / "c.txt"
    for p in [pdf, rar, txt]:
        p.write_text("x", encoding="utf-8")

    assert _is_supported_extension(pdf, settings) is True
    assert _is_supported_extension(rar, settings) is True
    assert _is_supported_extension(txt, settings) is False

