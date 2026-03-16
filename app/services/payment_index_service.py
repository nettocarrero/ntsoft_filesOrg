"""
Índice de pagamentos: varre output/.../pagamentos/, lê .meta.json e expõe
listas filtradas por vencimento (vencidos, hoje, próximos N dias).
Cache em memória de 60 segundos para evitar varredura pesada.
"""
from __future__ import annotations

import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List

from app.services.document_finance_parser import read_payment_meta_file


_CACHE_TTL_SEC = 60
_cache: tuple[float, List[Dict[str, Any]]] = (0.0, [])


def scan_payments(base_output_dir: Path) -> List[Dict[str, Any]]:
    """
    Percorre output/{loja}/{ano}/{mes}/pagamentos/, lê .meta.json de cada PDF
    e retorna lista de pagamentos com due_date (ignora os sem due_date).
    Resultado em cache por 60 segundos.
    """
    global _cache
    now = time.monotonic()
    if _cache[0] > 0 and (now - _cache[0]) < _CACHE_TTL_SEC:
        return _cache[1]

    base = Path(base_output_dir)
    if not base.exists() or not base.is_dir():
        _cache = (now, [])
        return []

    out: List[Dict[str, Any]] = []
    for store_dir in base.iterdir():
        if not store_dir.is_dir():
            continue
        store_code = store_dir.name
        for year_dir in store_dir.iterdir():
            if not year_dir.is_dir() or len(year_dir.name) != 4 or not year_dir.name.isdigit():
                continue
            for month_dir in year_dir.iterdir():
                if not month_dir.is_dir() or len(month_dir.name) != 2 or not month_dir.name.isdigit():
                    continue
                if 1 <= int(month_dir.name) <= 12:
                    pagamentos_dir = month_dir / "pagamentos"
                    if pagamentos_dir.is_dir():
                        _collect_from_dir(
                            pagamentos_dir, store_code, year_dir.name, month_dir.name, out
                        )
        # Estrutura legada: output/loja/pagamentos/ (sem ano/mês)
        pagamentos_legacy = store_dir / "pagamentos"
        if pagamentos_legacy.is_dir():
            _collect_from_dir(pagamentos_legacy, store_code, "", "", out)

    _cache = (now, out)
    return out


def _collect_from_dir(
    dir_path: Path,
    store_code: str,
    year: str,
    month: str,
    out: List[Dict[str, Any]],
) -> None:
    for f in dir_path.iterdir():
        if not f.is_file() or f.suffix.lower() != ".pdf":
            continue
        meta = read_payment_meta_file(f)
        if not meta or not meta.get("due_date"):
            continue
        # Ignorar pagamentos marcados como pagos/ignorados
        if meta.get("status") in ("paid", "ignored"):
            continue
        due = meta["due_date"]
        amount = meta.get("amount")
        out.append({
            "store": store_code,
            "file_name": f.name,
            "path": str(f.resolve()),
            "due_date": due,
            "amount": amount,
            "year": year,
            "month": month,
        })


def _parse_due(due: str) -> date | None:
    try:
        y, m, d = due[:10].split("-")
        return date(int(y), int(m), int(d))
    except (ValueError, IndexError):
        return None


def get_overdue_payments(base_output_dir: Path) -> List[Dict[str, Any]]:
    """Pagamentos com due_date anterior a hoje."""
    today = date.today()
    return [
        p for p in scan_payments(base_output_dir)
        if _parse_due(p["due_date"]) is not None and _parse_due(p["due_date"]) < today
    ]


def get_payments_due_today(base_output_dir: Path) -> List[Dict[str, Any]]:
    """Pagamentos que vencem hoje."""
    today = date.today()
    return [
        p for p in scan_payments(base_output_dir)
        if _parse_due(p["due_date"]) == today
    ]


def get_payments_due_in_days(base_output_dir: Path, days: int) -> List[Dict[str, Any]]:
    """Pagamentos que vencem em até N dias (a partir de amanhã; hoje não entra)."""
    today = date.today()
    end = today + timedelta(days=days)
    return [
        p for p in scan_payments(base_output_dir)
        if _parse_due(p["due_date"]) is not None
        and today < _parse_due(p["due_date"]) <= end
    ]
