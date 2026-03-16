"""
Painel de vencimentos: pagamentos vencidos, vencendo hoje e nos próximos dias.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse

from app.web.helpers import get_settings, list_output_stores
from app.services.payment_index_service import (
    get_overdue_payments,
    get_payments_due_today,
    get_payments_due_in_days,
    scan_payments,
    invalidate_cache,
)
from app.services.document_finance_parser import update_payment_status, update_payment_due_date
from app.services import extract_pdf_text


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
async def payments_page(
    request: Request,
    show_all: bool = Query(False, alias="all"),
):
    settings = get_settings()
    store_list = list_output_stores(settings.paths.output_dir, settings.aliases)
    store_names = {s["code"]: s["name"] for s in store_list}

    overdue = [
        _enrich_payment_item(dict(p), store_names)
        for p in get_overdue_payments(settings.paths.output_dir)
    ]
    due_today = [
        _enrich_payment_item(dict(p), store_names)
        for p in get_payments_due_today(settings.paths.output_dir)
    ]
    due_in_7 = [
        _enrich_payment_item(dict(p), store_names)
        for p in get_payments_due_in_days(settings.paths.output_dir, 7)
    ]

    all_payments = []
    if show_all:
        base_list = scan_payments(settings.paths.output_dir)
        all_payments = [
            _enrich_payment_item(dict(p), store_names) for p in base_list
        ]
        all_payments.sort(key=lambda x: (x.get("due_date") or "9999-12-31"))

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
            "show_all": show_all,
            "all_payments": all_payments,
        },
    )


@router.post("/payments/mark-paid", response_class=RedirectResponse)
async def mark_payment_as_paid(path: str = Form(...)):
    """
    Marca um pagamento como 'paid' no .meta.json correspondente.
    Após isso, ele deixa de aparecer nas listas de vencidos/pendentes.
    """
    pdf_path = Path(path)
    try:
        update_payment_status(pdf_path, status="paid")
        invalidate_cache()
    except Exception:
        # Em caso de erro, apenas ignora e volta para a tela
        pass
    return RedirectResponse(url="/payments", status_code=303)


@router.post("/payments/update-due-date", response_class=RedirectResponse)
async def update_due_date(path: str = Form(...), new_due_date: str = Form(...)):
    """
    Corrige manualmente a data de vencimento de um pagamento (YYYY-MM-DD).
    """
    pdf_path = Path(path)
    try:
        # Campo de input type="date" já vem no formato YYYY-MM-DD
        cleaned = (new_due_date or "").strip() or None
        update_payment_due_date(pdf_path, cleaned)
        invalidate_cache()
    except Exception:
        pass
    return RedirectResponse(url="/payments", status_code=303)


@router.get("/payments/text", response_class=HTMLResponse)
async def view_payment_text(request: Request, path: str = Query(..., description="Caminho absoluto do PDF")):
    """
    Mostra o texto extraído do PDF (modo debug/inspeção).
    """
    pdf_path = Path(path)
    if not pdf_path.exists() or not pdf_path.is_file():
        return HTMLResponse("<h1>Arquivo não encontrado</h1>", status_code=404)
    text, status = extract_pdf_text(pdf_path)
    return request.app.state.templates.TemplateResponse(
        "payment_text.html",
        {
            "request": request,
            "file_name": pdf_path.name,
            "path": str(pdf_path),
            "status": status,
            "text": text or "",
        },
    )
