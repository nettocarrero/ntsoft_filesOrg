from __future__ import annotations

import re
import unicodedata


def normalize_text(text: str) -> str:
    """
    Normaliza texto para comparação:
    - minúsculas
    - remove acentos
    - remove caracteres especiais não essenciais
    - colapsa espaços
    """
    if not text:
        return ""

    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

