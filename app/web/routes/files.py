from __future__ import annotations

from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Request, Query, Form
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse

from app.web.helpers import get_settings, list_output_stores, list_store_files

router = APIRouter()


def _parse_date(value: str | None):
    """Converte YYYY-MM-DD em date ou None."""
    if not value or not value.strip():
        return None
    try:
        return datetime.strptime(value.strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


@router.get("/files", response_class=HTMLResponse)
async def files_page(
    request: Request,
    store: str | None = Query(None),
    tipo: str | None = Query(None),
    nome: str | None = Query(None),
    data_de: str | None = Query(None, description="Data inicial (YYYY-MM-DD)"),
    data_ate: str | None = Query(None, description="Data final (YYYY-MM-DD)"),
    renamed: str | None = Query(None),
    deleted: str | None = Query(None),
):
    settings = get_settings()
    stores = list_output_stores(settings.paths.output_dir, settings.aliases)
    files: list = []
    store_name = ""
    date_from = _parse_date(data_de)
    date_to = _parse_date(data_ate)
    if store:
        store_name = next((s["name"] for s in stores if s["code"] == store), store)
        files = list_store_files(
            settings.paths.output_dir,
            store,
            doc_type_filter=tipo,
            name_filter=nome,
            date_from=date_from,
            date_to=date_to,
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
            "filter_data_de": data_de or "",
            "filter_data_ate": data_ate or "",
            "renamed": renamed == "1",
            "deleted": deleted == "1",
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


@router.get("/files/view")
async def files_view(
    path: str = Query(..., description="Caminho do arquivo"),
):
    """Abre o arquivo em nova aba (visualização inline, ex.: PDF)."""
    settings = get_settings()
    resolved = _resolve_output_path(path, settings.paths.output_dir)
    if not resolved:
        return {"error": "Arquivo não encontrado"}
    media_type = "application/pdf" if resolved.suffix.lower() == ".pdf" else None
    return FileResponse(
        resolved,
        filename=resolved.name,
        media_type=media_type,
        headers={"Content-Disposition": "inline"},
    )


@router.get("/files/rename", response_class=HTMLResponse)
async def files_rename_page(
    request: Request,
    path: str = Query(..., description="Caminho do arquivo"),
    store: str | None = Query(None),
):
    """Página com formulário para renomear o arquivo."""
    settings = get_settings()
    resolved = _resolve_output_path(path, settings.paths.output_dir)
    if not resolved:
        return HTMLResponse(content="<h1>Arquivo não encontrado</h1>", status_code=404)
    return request.app.state.templates.TemplateResponse(
        "files_rename.html",
        {
            "request": request,
            "path_value": str(resolved),
            "current_name": resolved.name,
            "store": store or "",
        },
    )


def _safe_basename(name: str) -> str:
    """Retorna apenas o nome do arquivo, sem path (segurança)."""
    return Path(name).name.strip() if name else ""


@router.post("/files/rename", response_class=RedirectResponse)
async def files_rename_do(
    path: str = Form(...),
    new_name: str = Form(...),
    store: str = Form(""),
):
    """Renomeia o arquivo (mesmo diretório). Redireciona de volta ao explorador."""
    settings = get_settings()
    resolved = _resolve_output_path(path, settings.paths.output_dir)
    if not resolved:
        return RedirectResponse(url="/files?error=arquivo_nao_encontrado", status_code=303)
    safe_name = _safe_basename(new_name)
    if not safe_name:
        return RedirectResponse(
            url=f"/files/rename?path={quote(path, safe='')}&store={quote(store, safe='')}&error=nome_vazio",
            status_code=303,
        )
    new_path = resolved.parent / safe_name
    if new_path.exists() and new_path != resolved:
        return RedirectResponse(
            url=f"/files/rename?path={quote(path, safe='')}&store={quote(store, safe='')}&error=ja_existe",
            status_code=303,
        )
    try:
        resolved.rename(new_path)
    except OSError:
        return RedirectResponse(
            url=f"/files/rename?path={quote(path, safe='')}&store={quote(store, safe='')}&error=erro",
            status_code=303,
        )
    back = f"/files?store={quote(store, safe='')}&renamed=1" if store else "/files?renamed=1"
    return RedirectResponse(url=back, status_code=303)


@router.post("/files/delete", response_class=RedirectResponse)
async def files_delete(
    path: str = Form(...),
    store: str = Form(""),
):
    """Exclui o arquivo. Redireciona de volta ao explorador."""
    settings = get_settings()
    resolved = _resolve_output_path(path, settings.paths.output_dir)
    if not resolved:
        return RedirectResponse(url="/files?error=arquivo_nao_encontrado", status_code=303)
    try:
        resolved.unlink()
    except OSError:
        return RedirectResponse(url="/files?error=erro_excluir", status_code=303)
    back = f"/files?store={quote(store, safe='')}&deleted=1" if store else "/files?deleted=1"
    return RedirectResponse(url=back, status_code=303)
