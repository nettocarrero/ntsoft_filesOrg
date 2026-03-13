from __future__ import annotations

from pathlib import Path
from typing import Tuple

import fitz  # PyMuPDF


def extract_pdf_text(path: Path) -> Tuple[str, str]:
    """
    Extrai texto de um PDF usando PyMuPDF.
    Retorna (texto, status), onde status pode ser:
    - "ok"
    - "texto_insuficiente"
    - "erro"
    """
    try:
        doc = fitz.open(path)
        texts = []
        for page in doc:
            texts.append(page.get_text())
        doc.close()
        full_text = "\n".join(texts).strip()
        if not full_text or len(full_text) < 20:
            return full_text, "texto_insuficiente"
        return full_text, "ok"
    except Exception:
        return "", "erro"

