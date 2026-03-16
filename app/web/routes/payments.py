"""
Painel de vencimentos: pagamentos vencidos, vencendo hoje e nos próximos dias.
"""
from __future__ import annotations

from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.web.helpers import get_settings, list_output_stores
from app.services.payment_index_service import (
    get_overdue_payments,
    get_payments_due_today,
    get_payments_due_in_days,
)


router = APIRouter()


def _parse_due(due: str) -> date | None:
    try:
        y, m, d = due[:10].split("-")
        return date(int(y), int(m), int(d))
    except (ValueError, IndexError):
        return None


def _format_date_br(iso_date: str) -> str:
    if not iso_date or len(iso_date) < 10:
        return "-"
    try:
        y, m, d = iso_date[:10].split("-")
        return f"{d}/{m}/{y}"
    except ValueError:
        return "-"


def _format_amount_br(value: float | None) -> str:
    if value is None:
        return "-"
    try:
        return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "-"


def _enrich_payment_item(item: dict, store_names: dict) -> dict:
    due = item.get("due_date")
    due_date = _parse_due(due) if due else None
    today = date.today()
    if due_date is not None:
        delta = (due_date - today).days
        item["days_remaining"] = delta
        if delta < 0:
            item["status"] = "overdue"
        elif delta == 0:
            item["status"] = "today"
        elif delta <= 7:
            item["status"] = "upcoming"
        else:
            item["status"] = "future"
    else:
        item["days_remaining"] = None
        item["status"] = "unknown"
    item["store_name"] = store_names.get(item["store"], item["store"])
    item["due_date_br"] = _format_date_br(due) if due else "-"
    item["amount_br"] = _format_amount_br(item.get("amount"))
    item["path_url"] = quote(item["path"], safe="")
    item["explorer_url"] = ""
    if item.get("year") and item.get("month"):
        item["explorer_url"] = f"/files?store={quote(item['store'], safe='')}&ano={item['year']}&mes={item['month']}&tipo=pagamentos"
    else:
        item["explorer_url"] = f"/files?store={quote(item['store'], safe='')}&tipo=pagamentos"
    return item


@router.get("/payments", response_class=HTMLResponse)
async def payments_page(request: Request):
    settings = get_settings()
    store_list = list_output_stores(settings.paths.output_dir, settings.aliases)
    store_names = {s["code"]: s["name"] for s in store_list}

    overdue = [ _enrich_payment_item(dict(p), store_names) for p in get_overdue_payments(settings.paths.output_dir) ]
    due_today = [ _enrich_payment_item(dict(p), store_names) for p in get_payments_due_today(settings.paths.output_dir) ]
    due_in_7 = [ _enrich_payment_item(dict(p), store_names) for p in get_payments_due_in_days(settings.paths.output_dir, 7) ]

    return request.app.state.templates.TemplateResponse(
        "payments.html",
        {
            "request": request,
            "overdue": overdue,
            "due_today": due_today,
            "due_in_7": due_in_7,
            "count_overdue": len(overdue),
            "count_today": len(due_today),
            "count_in_7": len(due_in_7),
        },
    )
