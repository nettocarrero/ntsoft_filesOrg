from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.web.helpers import get_settings, dashboard_stats

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    settings = get_settings()
    stats = dashboard_stats(settings.paths.reports_dir)
    return request.app.state.templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "stats": stats,
            "store_names": {
                "ljUbj": "Ubajara",
                "ljIbi": "Ibiapina",
                "ljSb": "São Benedito",
                "ljGba": "Guaraciaba",
                "ljLc": "L&C (Sobral)",
                "desconhecido": "Desconhecido",
            },
        },
    )
