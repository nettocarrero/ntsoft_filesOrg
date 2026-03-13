from __future__ import annotations

import zipfile
from pathlib import Path
from typing import List


def extract_zip(zip_path: Path, temp_dir: Path) -> List[Path]:
    """
    Extrai o ZIP para uma subpasta em temp, preservando a estrutura interna.
    Retorna a lista de todos os arquivos extraídos.
    """
    target_dir = temp_dir / zip_path.stem
    target_dir.mkdir(parents=True, exist_ok=True)

    extracted_files: List[Path] = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(target_dir)

    for path in target_dir.rglob("*"):
        if path.is_file():
            extracted_files.append(path)

    return extracted_files

