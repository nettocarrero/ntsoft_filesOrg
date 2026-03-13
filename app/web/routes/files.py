from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, FileResponse

from app.web.helpers import get_settings, list_output_stores, list_store_files

router = APIRouter()


@router.get("/files", response_class=HTMLResponse)
async def files_page(
    request: Request,
    store: str | None = Query(None),
    tipo: str | None = Query(None),
    nome: str | None = Query(None),
):
    settings = get_settings()
    stores = list_output_stores(settings.paths.output_dir, settings.aliases)
    files: list = []
    store_name = ""
    if store:
        store_name = next((s["name"] for s in stores if s["code"] == store), store)
        files = list_store_files(
            settings.paths.output_dir,
            store,
            doc_type_filter=tipo,
            name_filter=nome,
        )
        for f in files:
            f["path_url"] = quote(str(f["path"]), safe="")
    return request.app.state.templates.TemplateResponse(
        "files.html",
        {
            "request": request,
            "stores": stores,
            "selected_store": store,
            "store_name": store_name,
            "files": files,
            "filter_tipo": tipo or "",
            "filter_nome": nome or "",
        },
    )


def _resolve_output_path(path_str: str, output_dir: Path) -> Path | None:
    """Resolve path garantindo que está dentro de output_dir."""
    p = Path(path_str)
    if not p.is_absolute():
        p = output_dir / path_str
    try:
        resolved = p.resolve()
        output_resolved = output_dir.resolve()
        resolved.relative_to(output_resolved)
        return resolved if resolved.exists() and resolved.is_file() else None
    except (OSError, RuntimeError, ValueError):
        return None


@router.get("/files/download")
async def files_download(
    path: str = Query(..., description="Caminho do arquivo"),
):
    """Download do arquivo organizado."""
    settings = get_settings()
    resolved = _resolve_output_path(path, settings.paths.output_dir)
    if not resolved:
        return {"error": "Arquivo não encontrado"}
    return FileResponse(resolved, filename=resolved.name)
