from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, FileResponse

from app.web.helpers import get_settings, list_review_files

router = APIRouter()


@router.get("/review", response_class=HTMLResponse)
async def review_page(request: Request):
    settings = get_settings()
    files = list_review_files(settings.paths.review_manual_dir)
    for f in files:
        f["path_url"] = quote(str(f["path"]), safe="")
    return request.app.state.templates.TemplateResponse(
        "review.html",
        {"request": request, "files": files},
    )


def _resolve_review_path(path_str: str, review_dir: Path) -> Path | None:
    """Resolve path garantindo que está dentro de review_manual_dir."""
    p = Path(path_str)
    if not p.is_absolute():
        p = review_dir / path_str
    try:
        resolved = p.resolve()
        review_resolved = review_dir.resolve()
        resolved.relative_to(review_resolved)
        return resolved if resolved.exists() and resolved.is_file() else None
    except (OSError, RuntimeError, ValueError):
        return None


@router.get("/review/file")
async def review_file_view(
    path: str = Query(..., description="Caminho do arquivo em review_manual"),
):
    """Serve o arquivo para visualização (abre em nova aba em vez de baixar)."""
    settings = get_settings()
    resolved = _resolve_review_path(path, settings.paths.review_manual_dir)
    if not resolved:
        return {"error": "Arquivo não encontrado"}
    media_type = "application/pdf" if resolved.suffix.lower() == ".pdf" else None
    return FileResponse(
        resolved,
        filename=resolved.name,
        media_type=media_type,
        headers={"Content-Disposition": "inline"},
    )
