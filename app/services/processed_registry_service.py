from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any


def _registry_path(data_dir: Path) -> Path:
    return data_dir / "processed_input_registry.json"


def _load_registry(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_registry(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def is_already_processed(data_dir: Path, file_path: Path) -> bool:
    """Verifica se um arquivo (mesmo path, tamanho e mtime) já foi processado."""
    reg_path = _registry_path(data_dir)
    registry = _load_registry(reg_path)
    key = str(file_path.resolve())
    meta = registry.get(key)
    if not meta:
        return False
    try:
        st = file_path.stat()
    except OSError:
        return False
    return meta.get("size") == st.st_size and abs(meta.get("mtime", 0) - st.st_mtime) < 1e-3


def mark_as_processed(data_dir: Path, file_path: Path) -> None:
    """Marca um arquivo como processado (path absoluto, tamanho, mtime)."""
    reg_path = _registry_path(data_dir)
    registry = _load_registry(reg_path)
    try:
        st = file_path.stat()
    except OSError:
        return
    key = str(file_path.resolve())
    registry[key] = {"size": st.st_size, "mtime": st.st_mtime}
    _save_registry(reg_path, registry)


def clear_processed_registry(data_dir: Path) -> None:
    """Apaga o registro de arquivos processados (para forçar reprocessamento)."""
    reg_path = _registry_path(data_dir)
    try:
        if reg_path.exists():
            reg_path.unlink()
    except OSError:
        pass

