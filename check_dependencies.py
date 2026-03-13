from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List


def print_status(label: str, status: str, message: str) -> None:
    print(f"[{status}] {label}: {message}")


def check_python_version() -> None:
    major, minor = sys.version_info[:2]
    if major > 3 or (major == 3 and minor >= 12):
        print_status("Python", "OK", f"{major}.{minor}")
    else:
        print_status("Python", "ERROR", f"Versao {major}.{minor} encontrada, requer 3.12+")


def check_venv() -> None:
    venv_dir = Path(".venv")
    if venv_dir.exists():
        print_status("Ambiente virtual (.venv)", "OK", "Encontrado")
    else:
        print_status("Ambiente virtual (.venv)", "WARNING", "Nao encontrado. Rode setup_env.bat")


def check_packages() -> None:
    required = ["fitz", "pdf2image", "pytesseract", "watchdog", "rarfile"]
    missing: List[str] = []
    for pkg in required:
        try:
            __import__(pkg)
        except Exception:
            missing.append(pkg)
    if not missing:
        print_status("Pacotes Python principais", "OK", "Todos instalados")
    else:
        print_status(
            "Pacotes Python principais",
            "WARNING",
            f"Faltando: {', '.join(missing)}. Rode setup_env.bat ou pip install -r requirements.txt",
        )


def check_tesseract() -> None:
    from app.config import load_settings

    settings = load_settings()
    tesseract_cmd = settings.ocr.tesseract_cmd or "tesseract"
    # se caminho completo, testar se existe
    if Path(tesseract_cmd).is_file():
        print_status("Tesseract", "OK", f"Encontrado em {tesseract_cmd}")
        return

    cmd = shutil.which(tesseract_cmd)
    if cmd:
        print_status("Tesseract", "OK", f"Encontrado em PATH: {cmd}")
        return

    print_status(
        "Tesseract",
        "WARNING",
        "Nao encontrado. Instale Tesseract e/ou configure 'tesseract_cmd' em config.local.json (secao 'ocr').",
    )


def check_poppler() -> None:
    # tenta localizar pdfinfo ou pdftoppm
    pdfinfo = shutil.which("pdfinfo")
    pdftoppm = shutil.which("pdftoppm")
    if pdfinfo or pdftoppm:
        tool = pdfinfo or pdftoppm
        print_status("Poppler (pdf2image)", "OK", f"Ferramenta encontrada: {tool}")
    else:
        print_status(
            "Poppler (pdf2image)",
            "WARNING",
            "pdfinfo/pdftoppm nao encontrados no PATH. Instale Poppler e adicione ao PATH para OCR funcionar.",
        )


def check_paths() -> None:
    from app.config import load_settings

    settings = load_settings()
    paths = settings.paths
    for label, p in [
        ("input_dir", paths.input_dir),
        ("output_dir", paths.output_dir),
        ("temp_dir", paths.temp_dir),
        ("review_manual_dir", paths.review_manual_dir),
        ("reports_dir", paths.reports_dir),
        ("processed_input_dir", settings.processed_input.processed_dir),
    ]:
        if p.exists():
            print_status(label, "OK", str(p))
        else:
            print_status(label, "ERROR", f"Nao existe: {p}")


def check_whatsapp_source_dir() -> None:
    from app.config import load_settings

    settings = load_settings()
    cfg = settings.whatsapp_ingestion
    if not cfg.enabled:
        print_status("WhatsApp ingestion", "OK", "Desabilitado (enabled=False)")
        return

    if not cfg.source_dir:
        print_status(
            "WhatsApp ingestion",
            "ERROR",
            "enabled=True mas 'source_dir' nao configurado em config.local.json",
        )
        return

    if cfg.source_dir.exists():
        print_status("WhatsApp ingestion source_dir", "OK", str(cfg.source_dir))
    else:
        print_status(
            "WhatsApp ingestion source_dir",
            "ERROR",
            f"Pasta nao existe: {cfg.source_dir}",
        )


def main() -> None:
    print("=== Verificacao de dependencias ntsoft-orgfiles ===")
    print(f"Sistema operacional: {platform.system()} {platform.release()}")
    check_python_version()
    check_venv()
    check_packages()
    check_tesseract()
    check_poppler()
    check_paths()
    check_whatsapp_source_dir()


if __name__ == "__main__":
    main()

