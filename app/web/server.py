"""
Servidor web do painel local.
Não inicia watcher nem ingestão WhatsApp; apenas consulta dados existentes.
"""
from __future__ import annotations

import socket
import webbrowser
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.web.routes import dashboard_router, review_router, files_router, config_router

APP_ROOT = Path(__file__).resolve().parent

templates = Jinja2Templates(directory=str(APP_ROOT / "templates"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.templates = templates
    yield


app = FastAPI(title="Organizador de Documentos", description="Painel local", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(APP_ROOT / "static")), name="static")


app.include_router(dashboard_router, tags=["dashboard"])
app.include_router(review_router, tags=["review"])
app.include_router(files_router, tags=["files"])
app.include_router(config_router, tags=["config"])


def _get_local_ip() -> str | None:
    """Retorna o IPv4 principal da máquina na rede local (ex.: 192.168.0.12)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(0.5)
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except (OSError, socket.error):
        return None


def main():
    import uvicorn
    host = "0.0.0.0"
    port = 8000
    local_url = f"http://localhost:{port}"
    webbrowser.open(local_url)
    local_ip = _get_local_ip()
    print("Servidor web iniciado.")
    print()
    print("Painel disponível em:")
    print(f"  {local_url}")
    if local_ip:
        print(f"  http://{local_ip}:{port}")
    else:
        print("  (IP da rede local não detectado automaticamente)")
    print()
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
