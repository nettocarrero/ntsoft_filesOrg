from __future__ import annotations

from pathlib import Path
from typing import List
import re


_INVALID_WIN_CHARS = r'<>:"/\\|?*'
_INVALID_WIN_RE = re.compile(f"[{re.escape(_INVALID_WIN_CHARS)}]")


def sanitize_windows_path_part(name: str) -> str:
    """
    Sanitiza uma parte de caminho (um diretório ou nome de arquivo) para Windows.
    - remove espaços no início e fim
    - remove pontos no final
    - remove caracteres inválidos (< > : \" / \\ | ? *)
    - remove espaços e pontos imediatamente antes da extensão (ex.: "arquivo .pdf" -> "arquivo.pdf")
    - evita nomes vazios, retornando 'unnamed' como fallback
    """
    if not name:
        return "unnamed"

    cleaned = name.strip()
    # remove caracteres inválidos
    cleaned = _INVALID_WIN_RE.sub("", cleaned)

    # tratar padrão "nome .ext" ou "nome . ext"
    m = re.match(r"^(.*?)[\s\.]+(\.[^.]+)$", cleaned)
    if m:
        base, ext = m.group(1), m.group(2)
        cleaned = base.rstrip().rstrip(".") + ext

    # remove pontos finais remanescentes
    cleaned = cleaned.rstrip(".").strip()

    if not cleaned:
        return "unnamed"
    return cleaned


def sanitize_archive_member_path(path_str: str) -> Path:
    """
    Sanitiza o caminho completo de um membro de arquivo compactado.
    - normaliza separadores para '/'
    - evita path traversal ('..') e partes vazias
    - aplica sanitize_windows_path_part em cada parte
    """
    # normaliza separadores
    normalized = path_str.replace("\\", "/")
    parts: List[str] = []
    for part in normalized.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            # ignora tentativas de sair da pasta destino
            continue
        safe_part = sanitize_windows_path_part(part)
        parts.append(safe_part)

    if not parts:
        return Path("unnamed")

    return Path(*parts)

