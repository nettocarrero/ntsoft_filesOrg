from __future__ import annotations

import shutil
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Request, Query, Form
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse

from app.models.enums import DocumentType
from app.web.helpers import get_settings, list_review_files, list_output_stores

router = APIRouter()

DOC_TYPES = [t.value for t in DocumentType]


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


def _safe_destination(parent: Path, filename: str) -> Path:
    """Gera path em parent sem sobrescrever (sufixo (1), (2) se necessário)."""
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    candidate = parent / f"{stem}{suffix}"
    n = 1
    while candidate.exists():
        candidate = parent / f"{stem} ({n}){suffix}"
        n += 1
    return candidate


@router.get("/review/correct", response_class=HTMLResponse)
async def review_correct_page(
    request: Request,
    path: str = Query(..., description="Caminho do arquivo em review_manual"),
):
    """Página para escolher loja e tipo e enviar o arquivo para a pasta correta."""
    settings = get_settings()
    resolved = _resolve_review_path(path, settings.paths.review_manual_dir)
    if not resolved:
        return HTMLResponse(content="<h1>Arquivo não encontrado</h1>", status_code=404)
    stores = list_output_stores(settings.paths.output_dir, settings.aliases)
    return request.app.state.templates.TemplateResponse(
        "review_correct.html",
        {
            "request": request,
            "path_value": str(resolved),
            "path_url": quote(str(resolved), safe=""),
            "file_name": resolved.name,
            "stores": stores,
            "doc_types": DOC_TYPES,
        },
    )


@router.post("/review/correct", response_class=RedirectResponse)
async def review_correct_do(
    path: str = Form(...),
    store: str = Form(...),
    doc_type: str = Form(...),
):
    """Move o arquivo de review_manual para output/store/doc_type/."""
    settings = get_settings()
    resolved = _resolve_review_path(path, settings.paths.review_manual_dir)
    if not resolved:
        return RedirectResponse(url="/review?error=arquivo_nao_encontrado", status_code=303)
    store = (store or "").strip()
    doc_type = (doc_type or "").strip().lower()
    if not store or not doc_type:
        return RedirectResponse(
            url=f"/review/correct?path={quote(path, safe='')}&error=preencha_loja_tipo",
            status_code=303,
        )
    if doc_type not in DOC_TYPES:
        return RedirectResponse(
            url=f"/review/correct?path={quote(path, safe='')}&error=tipo_invalido",
            status_code=303,
        )
    # Pastas em output: apenas caracteres seguros (evitar path traversal)
    if "/" in store or "\\" in store or ".." in store:
        return RedirectResponse(url="/review?error=loja_invalida", status_code=303)
    if "/" in doc_type or "\\" in doc_type or ".." in doc_type:
        return RedirectResponse(url="/review?error=tipo_invalido", status_code=303)
    dest_dir = settings.paths.output_dir / store / doc_type
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_file = _safe_destination(dest_dir, resolved.name)
    try:
        shutil.move(str(resolved), str(dest_file))
    except OSError:
        return RedirectResponse(url="/review?error=erro_ao_mover", status_code=303)
    return RedirectResponse(url="/review?corrected=1", status_code=303)


@router.get("/review/discard", response_class=HTMLResponse)
async def review_discard_page(
    request: Request,
    path: str = Query(..., description="Caminho do arquivo em review_manual"),
):
    """Página de confirmação para descartar (excluir) o arquivo."""
    settings = get_settings()
    resolved = _resolve_review_path(path, settings.paths.review_manual_dir)
    if not resolved:
        return HTMLResponse(content="<h1>Arquivo não encontrado</h1>", status_code=404)
    return request.app.state.templates.TemplateResponse(
        "review_discard.html",
        {
            "request": request,
            "path_value": str(resolved),
            "path_url": quote(str(resolved), safe=""),
            "file_name": resolved.name,
        },
    )


@router.post("/review/discard", response_class=RedirectResponse)
async def review_discard_do(path: str = Form(...)):
    """Exclui o arquivo de review_manual (descartar)."""
    settings = get_settings()
    resolved = _resolve_review_path(path, settings.paths.review_manual_dir)
    if not resolved:
        return RedirectResponse(url="/review?error=arquivo_nao_encontrado", status_code=303)
    try:
        resolved.unlink()
    except OSError:
        return RedirectResponse(url="/review?error=erro_ao_excluir", status_code=303)
    return RedirectResponse(url="/review?discarded=1", status_code=303)
