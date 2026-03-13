from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any
import json


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class ConfidenceThresholds:
    store_min_score: int = 8
    store_margin: int = 4
    doc_type_min_score: int = 6
    doc_type_margin: int = 3


@dataclass
class PathsConfig:
    input_dir: Path = PROJECT_ROOT / "input"
    output_dir: Path = PROJECT_ROOT / "output"
    temp_dir: Path = PROJECT_ROOT / "temp"
    review_manual_dir: Path = PROJECT_ROOT / "review_manual"
    reports_dir: Path = PROJECT_ROOT / "reports"
    data_dir: Path = PROJECT_ROOT / "app" / "data"


@dataclass
class ProcessedInputConfig:
    # "keep" | "move" | "delete"
    action: str = "move"
    processed_dir: Path = PROJECT_ROOT / "processed_input"


@dataclass
class ScoringConfig:
    store_weights: Dict[str, int]
    # Example keys: "folder_match", "filename_match", "text_match", "zip_name_match"


@dataclass
class OCRConfig:
    enabled: bool = True
    language: str = "por"
    dpi: int = 200
    min_text_length_trigger: int = 50
    max_pages: int | None = None
    tesseract_cmd: str | None = None


@dataclass
class WhatsAppIngestionConfig:
    enabled: bool = False
    source_dir: Path | None = None
    recursive: bool = True
    copy_supported_extensions: list[str] = field(
        default_factory=lambda: [".pdf", ".zip", ".rar"]
    )
    stabilize_timeout: int = 30
    stabilize_interval: float = 1.0
    startup_scan: bool = True


@dataclass
class Settings:
    paths: PathsConfig
    thresholds: ConfidenceThresholds
    scoring: ScoringConfig
    aliases: Dict[str, Any]
    document_keywords: Dict[str, Any]
    processed_input: ProcessedInputConfig
    ocr: OCRConfig
    whatsapp_ingestion: WhatsAppIngestionConfig


def ensure_directories(paths: PathsConfig) -> None:
    # limpa pasta temp para evitar acúmulo de arquivos antigos
    if paths.temp_dir.exists():
        for child in paths.temp_dir.iterdir():
            if child.is_file():
                child.unlink(missing_ok=True)
            else:
                import shutil

                shutil.rmtree(child, ignore_errors=True)

    for path in [
        paths.input_dir,
        paths.output_dir,
        paths.temp_dir,
        paths.review_manual_dir,
        paths.reports_dir,
    ]:
        path.mkdir(parents=True, exist_ok=True)


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _deep_update_dict(original: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in updates.items():
        if (
            key in original
            and isinstance(original[key], dict)
            and isinstance(value, dict)
        ):
            original[key] = _deep_update_dict(original[key], value)
        else:
            original[key] = value
    return original


def _apply_local_overrides(settings: Settings) -> Settings:
    """
    Aplica overrides vindos de config.local.json, se existir, sem exigir
    alteração de código por máquina.
    """
    local_cfg_path = PROJECT_ROOT / "config.local.json"
    if not local_cfg_path.exists():
        return settings

    try:
        raw = load_json(local_cfg_path)
    except Exception:
        return settings

    # Paths (converter strings para Path quando apropriado)
    paths_data = raw.get("paths")
    if isinstance(paths_data, dict):
        serializable: Dict[str, Any] = {}
        for k, v in paths_data.items():
            if isinstance(v, str) and k.endswith("_dir"):
                serializable[k] = Path(v)
            else:
                serializable[k] = v
        data = settings.paths.__dict__
        merged = _deep_update_dict(data, serializable)
        settings.paths = PathsConfig(**merged)

    # Processed input (converter processed_dir em Path se string)
    pi_data = raw.get("processed_input")
    if isinstance(pi_data, dict):
        serializable_pi: Dict[str, Any] = {}
        for k, v in pi_data.items():
            if k == "processed_dir" and isinstance(v, str):
                serializable_pi[k] = Path(v)
            else:
                serializable_pi[k] = v
        data = settings.processed_input.__dict__
        merged = _deep_update_dict(data, serializable_pi)
        settings.processed_input = ProcessedInputConfig(**merged)

    # OCR
    ocr_data = raw.get("ocr")
    if isinstance(ocr_data, dict):
        data = settings.ocr.__dict__
        merged = _deep_update_dict(data, ocr_data)
        settings.ocr = OCRConfig(**merged)

    # WhatsApp ingestion
    wa_data = raw.get("whatsapp_ingestion")
    if isinstance(wa_data, dict):
        serializable = {}
        for k, v in wa_data.items():
            if k == "source_dir" and isinstance(v, str):
                serializable[k] = Path(v)
            else:
                serializable[k] = v
        data = settings.whatsapp_ingestion.__dict__
        merged = _deep_update_dict(data, serializable)
        settings.whatsapp_ingestion = WhatsAppIngestionConfig(**merged)

    return settings

def load_settings() -> Settings:
    paths = PathsConfig()
    ensure_directories(paths)

    aliases_path = paths.data_dir / "aliases.json"
    document_keywords_path = paths.data_dir / "document_keywords.json"

    aliases = load_json(aliases_path)
    document_keywords = load_json(document_keywords_path)

    thresholds = ConfidenceThresholds()
    scoring = ScoringConfig(
        store_weights={
            "folder_match": 8,
            "filename_match": 4,
            "text_match": 6,
            "zip_name_match": 5,
        }
    )
    processed_input = ProcessedInputConfig()
    processed_input.processed_dir.mkdir(parents=True, exist_ok=True)
    ocr = OCRConfig()
    whatsapp_ingestion = WhatsAppIngestionConfig()

    settings = Settings(
        paths=paths,
        thresholds=thresholds,
        scoring=scoring,
        aliases=aliases,
        document_keywords=document_keywords,
        processed_input=processed_input,
        ocr=ocr,
        whatsapp_ingestion=whatsapp_ingestion,
    )

    settings = _apply_local_overrides(settings)
    return settings

