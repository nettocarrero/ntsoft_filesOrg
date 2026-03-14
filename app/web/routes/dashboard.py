from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse

from app.web.helpers import get_settings, dashboard_stats, archive_reports, is_local_client, system_status

router = APIRouter()


def _format_ultima_varredura(iso_or_stem: str | None) -> str:
    """Formata ultima_execucao para exibição (ex.: 2025-03-13T12:34:56 -> 13/03 12:34)."""
    if not iso_or_stem:
        return "—"
    s = str(iso_or_stem)
    if "T" in s:
        try:
            date_part, time_part = s.split("T")[0], s.split("T")[1][:5]
            y, m, d = date_part.split("-")
            return f"{d}/{m} {time_part}"
        except Exception:
            return s
    return s


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, counters_reset: str | None = None):
    settings = get_settings()
    stats = dashboard_stats(settings.paths.reports_dir)
    status = system_status(settings)
    status["ultima_varredura_display"] = _format_ultima_varredura(status.get("ultima_execucao"))
    client_host = request.client.host if request.client else None
    allow_management = is_local_client(client_host)
    return request.app.state.templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "stats": stats,
            "status": status,
            "store_names": {
                "ljUbj": "Ubajara",
                "ljIbi": "Ibiapina",
                "ljSb": "São Benedito",
                "ljGba": "Guaraciaba",
                "ljLc": "L&C (Sobral)",
                "ljKlc": "KLC (Sobral)",
                "desconhecido": "Desconhecido",
            },
            "counters_reset": counters_reset,
            "allow_management": allow_management,
        },
    )


@router.post("/reset-counters", response_class=RedirectResponse)
async def reset_counters(request: Request):
    """Arquiva os relatórios atuais; os contadores zeram. Apenas localhost."""
    if not is_local_client(request.client.host if request.client else None):
        return PlainTextResponse("Apenas o PC principal (localhost) pode zerar os contadores.", status_code=403)
    settings = get_settings()
    count, archive_path = archive_reports(settings.paths.reports_dir)
    # Redireciona com info: 1 = sucesso (pode ser 0 arquivos se já estava vazio)
    return RedirectResponse(
        url=f"/?counters_reset=1&archived={count}&path={archive_path.name if archive_path else ''}",
        status_code=303,
    )
