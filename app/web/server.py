"""
Servidor web do painel local.
Não inicia watcher nem ingestão WhatsApp; apenas consulta dados existentes.
"""
from __future__ import annotations

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


def main():
    import uvicorn
    host = "127.0.0.1"
    port = 8000
    url = f"http://{host}:{port}"
    webbrowser.open(url)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
