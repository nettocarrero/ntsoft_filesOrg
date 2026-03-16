from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse

from app.config import PROJECT_ROOT, save_local_config
from app.web.helpers import (
    get_settings,
    system_status,
    is_local_client,
    load_ip_users,
    save_ip_users,
    clear_processed_input_registry,
)

router = APIRouter()


def start_watcher_in_new_terminal() -> bool:
    """
    Abre uma nova janela do terminal e executa `python -m app.main --watch`.
    Retorna True se o comando foi disparado com sucesso (Windows).
    """
    python_exe = Path(sys.executable).resolve()
    cwd = str(PROJECT_ROOT.resolve())
    cmd = f'"{python_exe}" -m app.main --watch'
    try:
        if sys.platform == "win32":
            # Nova janela CMD com título "Identificador"
            subprocess.Popen(
                f'start "Identificador" cmd /k "cd /d "{cwd}" && {cmd}"',
                cwd=cwd,
                shell=True,
            )
            return True
        # Linux/macOS: tente abrir terminal (gnome-terminal, xterm, etc.)
        if sys.platform == "darwin":
            subprocess.Popen(
                ["open", "-a", "Terminal", "-n", "--args", "bash", "-c", f"cd {cwd!r} && {python_exe} -m app.main --watch; exec bash"],
                cwd=cwd,
            )
            return True
        subprocess.Popen(
            ["xterm", "-e", f"cd {cwd!r} && {python_exe} -m app.main --watch; exec bash"],
            cwd=cwd,
        )
        return True
    except (OSError, Exception):
        return False


def _config_dict(settings):
    """Dicionário com valores atuais para o formulário."""
    return {
        "input_dir": str(settings.paths.input_dir),
        "output_dir": str(settings.paths.output_dir),
        "review_manual_dir": str(settings.paths.review_manual_dir),
        "reports_dir": str(settings.paths.reports_dir),
        "temp_dir": str(settings.paths.temp_dir),
        "processed_dir": str(settings.processed_input.processed_dir),
        "processed_action": settings.processed_input.action,
        "ocr_enabled": settings.ocr.enabled,
        "ocr_language": settings.ocr.language,
        "ocr_dpi": settings.ocr.dpi,
        "whatsapp_ingestion_enabled": settings.whatsapp_ingestion.enabled,
        "whatsapp_source_dir": str(settings.whatsapp_ingestion.source_dir) if settings.whatsapp_ingestion.source_dir else "",
    }


@router.get("/config", response_class=HTMLResponse)
async def config_page(
    request: Request,
    saved: str | None = None,
    watcher_started: str | None = None,
):
    settings = get_settings()
    status = system_status(settings)
    config = _config_dict(settings)
    ip_users = load_ip_users()
    client_host = request.client.host if request.client else None
    allow_management = is_local_client(client_host)
    return request.app.state.templates.TemplateResponse(
        "config.html",
        {
            "request": request,
            "config": config,
            "status": status,
            "ip_users": ip_users,
            "saved": saved == "1",
            "watcher_started": watcher_started == "1",
            "watcher_started_error": watcher_started == "0",
            "allow_management": allow_management,
        },
    )


def _checkbox_bool(value: str | None) -> bool:
    return value in ("on", "true", "1", "yes")


@router.post("/config", response_class=RedirectResponse)
async def config_save(
    request: Request,
    input_dir: str = Form(...),
    output_dir: str = Form(...),
    review_manual_dir: str = Form(...),
    reports_dir: str = Form(...),
    temp_dir: str = Form(...),
    processed_dir: str = Form(...),
    processed_action: str = Form("move"),
    ocr_enabled: str | None = Form(None),
    ocr_language: str = Form("por"),
    ocr_dpi: str = Form("200"),
    whatsapp_ingestion_enabled: str | None = Form(None),
    whatsapp_source_dir: str = Form(""),
):
    if not is_local_client(request.client.host if request.client else None):
        return PlainTextResponse("Apenas o PC principal (localhost) pode alterar configurações.", status_code=403)
    updates = {
        "paths": {
            "input_dir": input_dir.strip(),
            "output_dir": output_dir.strip(),
            "review_manual_dir": review_manual_dir.strip(),
            "reports_dir": reports_dir.strip(),
            "temp_dir": temp_dir.strip(),
        },
        "processed_input": {
            "processed_dir": processed_dir.strip(),
            "action": processed_action.strip() or "move",
        },
        "ocr": {
            "enabled": _checkbox_bool(ocr_enabled),
            "language": ocr_language.strip() or "por",
            "dpi": max(72, min(600, int(ocr_dpi) if str(ocr_dpi).strip().isdigit() else 200)),
        },
        "whatsapp_ingestion": {
            "enabled": _checkbox_bool(whatsapp_ingestion_enabled),
            "source_dir": whatsapp_source_dir.strip() or None,
        },
    }
    save_local_config(updates)
    return RedirectResponse(url="/config?saved=1", status_code=303)


@router.post("/start-watcher", response_class=RedirectResponse)
async def start_watcher(request: Request):
    """Abre uma nova janela do terminal com o identificador (watcher) em execução. Apenas localhost."""
    if not is_local_client(request.client.host if request.client else None):
        return PlainTextResponse("Apenas o PC principal (localhost) pode iniciar o identificador.", status_code=403)
    ok = start_watcher_in_new_terminal()
    return RedirectResponse(
        url="/config?watcher_started=1" if ok else "/config?watcher_started=0",
        status_code=303,
    )


@router.post("/config/processed-registry/clear", response_class=RedirectResponse)
async def config_clear_processed_registry(request: Request):
    """Limpa o registro de arquivos de input já processados (força reprocessamento)."""
    if not is_local_client(request.client.host if request.client else None):
        return PlainTextResponse("Apenas o PC principal pode limpar o cache de arquivos processados.", status_code=403)
    clear_processed_input_registry()
    return RedirectResponse(url="/config?saved=1", status_code=303)


@router.post("/config/ip-users", response_class=RedirectResponse)
async def config_ip_users(
    request: Request,
    action: str = Form(...),
    ip: str = Form(""),
    name: str = Form(""),
):
    """Adiciona ou remove vínculo IP -> nome de usuário (apenas localhost)."""
    if not is_local_client(request.client.host if request.client else None):
        return PlainTextResponse("Apenas o PC principal pode editar o mapeamento.", status_code=403)
    mapping = load_ip_users()
    ip = ip.strip()
    if action == "add" and ip:
        mapping[ip] = name.strip()
        save_ip_users(mapping)
    elif action == "remove" and ip:
        mapping.pop(ip, None)
        save_ip_users(mapping)
    return RedirectResponse(url="/config#ip-users", status_code=303)
