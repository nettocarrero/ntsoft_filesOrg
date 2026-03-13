from __future__ import annotations

from pathlib import Path


def is_pdf(path: Path) -> bool:
    return path.suffix.lower() == ".pdf"


def is_zip(path: Path) -> bool:
    return path.suffix.lower() == ".zip"


def is_rar(path: Path) -> bool:
    return path.suffix.lower() == ".rar"

