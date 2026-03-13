from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.web.helpers import get_settings, dashboard_stats, archive_reports

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, counters_reset: str | None = None):
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
            "counters_reset": counters_reset,
        },
    )


@router.post("/reset-counters", response_class=RedirectResponse)
async def reset_counters():
    """Arquiva os relatórios atuais; os contadores do dashboard zeram e você pode iniciar o monitoramento do zero."""
    settings = get_settings()
    count, archive_path = archive_reports(settings.paths.reports_dir)
    # Redireciona com info: 1 = sucesso (pode ser 0 arquivos se já estava vazio)
    return RedirectResponse(
        url=f"/?counters_reset=1&archived={count}&path={archive_path.name if archive_path else ''}",
        status_code=303,
    )
