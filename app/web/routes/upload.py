"""
Envio de arquivos para classificação: salva em input/, registra observação e IP, e roda o pipeline.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse

from app.config import load_settings
from app.logger import setup_logging
from app.main import process_input_files

router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".zip", ".rar"}


def _safe_destination(input_dir: Path, original_name: str) -> Path:
    """Gera path em input_dir sem sobrescrever (sufixo " (1)", " (2)" se necessário)."""
    base = Path(original_name).stem
    ext = Path(original_name).suffix.lower()
    candidate = input_dir / f"{base}{ext}"
    counter = 1
    while candidate.exists():
        candidate = input_dir / f"{base} ({counter}){ext}"
        counter += 1
    return candidate


def _save_upload_metadata(reports_dir: Path, observation: str, ip: str, filenames: list[str], saved_paths: list[str]) -> Path:
    """Registra observação, IP e arquivos em reports/upload_log/."""
    log_dir = reports_dir / "upload_log"
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = log_dir / f"upload_{stamp}_{ip.replace('.', '_').replace(':', '_')}.json"
    data = {
        "timestamp": datetime.now().isoformat(),
        "ip": ip,
        "observation": observation,
        "filenames": filenames,
        "saved_paths": saved_paths,
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


@router.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request):
    """Formulário: observação (obrigatória), arquivos, exibe IP do remetente."""
    client_ip = request.client.host if request.client else "—"
    return request.app.state.templates.TemplateResponse(
        "upload.html",
        {"request": request, "client_ip": client_ip},
    )


@router.post("/upload", response_class=RedirectResponse)
async def upload_submit(
    request: Request,
    observation: str = Form(..., min_length=1),
    files: list[UploadFile] = File(default=[]),
):
    """Recebe observação e arquivos; salva em input/, registra metadata (obs + IP), executa pipeline."""
    client_ip = request.client.host if request.client else "desconhecido"
    settings = load_settings()
    settings.paths.input_dir.mkdir(parents=True, exist_ok=True)

    if not files:
        return RedirectResponse(url="/upload?error=nenhum_arquivo", status_code=303)

    allowed = [f for f in files if Path(f.filename or "").suffix.lower() in ALLOWED_EXTENSIONS]
    if not allowed:
        return RedirectResponse(url="/upload?error=extensao_invalida", status_code=303)

    saved_paths: list[Path] = []
    filenames: list[str] = []

    for uf in allowed:
        name = uf.filename or "arquivo"
        dest = _safe_destination(settings.paths.input_dir, name)
        content = await uf.read()
        dest.write_bytes(content)
        saved_paths.append(dest)
        filenames.append(name)

    _save_upload_metadata(
        settings.paths.reports_dir,
        observation.strip(),
        client_ip,
        filenames,
        [str(p) for p in saved_paths],
    )

    setup_logging()
    try:
        await asyncio.to_thread(process_input_files, saved_paths, settings)
    except Exception:
        return RedirectResponse(url="/upload?error=erro_processamento", status_code=303)

    return RedirectResponse(url="/upload?success=1", status_code=303)
