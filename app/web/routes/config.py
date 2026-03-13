from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.web.helpers import get_settings, system_status

router = APIRouter()


@router.get("/config", response_class=HTMLResponse)
async def config_page(request: Request):
    settings = get_settings()
    status = system_status(settings)
    config_readonly = {
        "input_dir": str(settings.paths.input_dir),
        "output_dir": str(settings.paths.output_dir),
        "review_manual_dir": str(settings.paths.review_manual_dir),
        "reports_dir": str(settings.paths.reports_dir),
        "temp_dir": str(settings.paths.temp_dir),
        "ocr_enabled": settings.ocr.enabled,
        "ocr_language": settings.ocr.language,
        "whatsapp_ingestion_enabled": settings.whatsapp_ingestion.enabled,
        "whatsapp_source_dir": str(settings.whatsapp_ingestion.source_dir) if settings.whatsapp_ingestion.source_dir else None,
    }
    return request.app.state.templates.TemplateResponse(
        "config.html",
        {
            "request": request,
            "config": config_readonly,
            "status": status,
        },
    )
