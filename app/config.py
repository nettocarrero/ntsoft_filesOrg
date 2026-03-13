from __future__ import annotations

from dataclasses import dataclass
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
class Settings:
    paths: PathsConfig
    thresholds: ConfidenceThresholds
    scoring: ScoringConfig
    aliases: Dict[str, Any]
    document_keywords: Dict[str, Any]
    processed_input: ProcessedInputConfig
    ocr: OCRConfig


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

    return Settings(
        paths=paths,
        thresholds=thresholds,
        scoring=scoring,
        aliases=aliases,
        document_keywords=document_keywords,
        processed_input=processed_input,
        ocr=ocr,
    )

