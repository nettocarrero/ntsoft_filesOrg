from __future__ import annotations

from pathlib import Path
from typing import List

from app.utils.file_utils import is_pdf, is_zip, is_rar


def scan_input_files(input_dir: Path) -> List[Path]:
    """
    Retorna a lista de arquivos relevantes na pasta de entrada:
    - PDFs
    - ZIPs
    (apenas nível atual, sem recursão em subpastas da entrada neste primeiro momento)
    """
    files: List[Path] = []
    if not input_dir.exists():
        return files

    for entry in input_dir.iterdir():
        if entry.is_file() and (is_pdf(entry) or is_zip(entry) or is_rar(entry)):
            files.append(entry)
    return files

