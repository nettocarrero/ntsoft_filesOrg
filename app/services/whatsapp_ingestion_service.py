from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Set, Tuple

from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileMovedEvent
from watchdog.observers import Observer

from app.config import Settings
from app.utils.file_utils import is_pdf, is_zip, is_rar
from app.services.watcher_service import wait_until_file_is_ready


logger = logging.getLogger(__name__)


def _is_supported_extension(path: Path, settings: Settings) -> bool:
    return path.suffix.lower() in {
        ext.lower() for ext in settings.whatsapp_ingestion.copy_supported_extensions
    } and (is_pdf(path) or is_zip(path) or is_rar(path))


def _generate_safe_destination(input_dir: Path, original_name: str) -> Path:
    """
    Gera um nome de arquivo que não conflita em input/,
    usando sufixos " (1)", " (2)", etc. antes da extensão.
    """
    base = Path(original_name).stem
    ext = Path(original_name).suffix
    candidate = input_dir / f"{base}{ext}"
    counter = 1

    while candidate.exists():
        candidate = input_dir / f"{base} ({counter}){ext}"
        counter += 1

    return candidate


class WhatsAppIngestionHandler(FileSystemEventHandler):
    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.settings = settings
        self._processed_signatures: Set[Tuple[str, int, float]] = set()
        self._lock = threading.Lock()
        self._max_signatures = 1000

    def _already_ingested(self, path: Path) -> bool:
        try:
            st = path.stat()
        except FileNotFoundError:
            return False
        sig = (str(path), st.st_size, st.st_mtime)
        with self._lock:
            if sig in self._processed_signatures:
                return True
            if len(self._processed_signatures) >= self._max_signatures:
                self._processed_signatures.clear()
            self._processed_signatures.add(sig)
        return False

    def _handle_source_file(self, path: Path) -> None:
        if not _is_supported_extension(path, self.settings):
            logger.info("Arquivo ignorado por extensão não suportada (WhatsApp): %s", path)
            return

        cfg = self.settings.whatsapp_ingestion
        logger.info("Arquivo detectado na pasta do WhatsApp: %s", path)

        if not wait_until_file_is_ready(
            path, timeout=cfg.stabilize_timeout, interval=cfg.stabilize_interval
        ):
            logger.warning(
                "Arquivo do WhatsApp não ficou pronto a tempo, ignorando por agora: %s",
                path,
            )
            return

        if self._already_ingested(path):
            logger.info("Arquivo já ingerido anteriormente, ignorando: %s", path)
            return

        input_dir = self.settings.paths.input_dir
        input_dir.mkdir(parents=True, exist_ok=True)
        dest = _generate_safe_destination(input_dir, path.name)

        try:
            import shutil

            shutil.copy2(path, dest)
            logger.info("Arquivo copiado da pasta do WhatsApp para input: %s -> %s", path, dest)
        except Exception as exc:
            logger.error("Erro ao copiar arquivo do WhatsApp para input %s: %s", path, exc)

    def on_created(self, event: FileCreatedEvent) -> None:
        if event.is_directory:
            return
        path = Path(event.src_path)
        threading.Thread(target=self._handle_source_file, args=(path,), daemon=True).start()

    def on_moved(self, event: FileMovedEvent) -> None:
        if event.is_directory:
            return
        dest = Path(event.dest_path)
        threading.Thread(target=self._handle_source_file, args=(dest,), daemon=True).start()


def _startup_scan(settings: Settings, handler: WhatsAppIngestionHandler) -> None:
    cfg = settings.whatsapp_ingestion
    source_dir = cfg.source_dir
    if not source_dir or not source_dir.exists():
        return
    logger.info("Iniciando startup_scan na pasta do WhatsApp: %s", source_dir)
    pattern_iter = source_dir.rglob("*") if cfg.recursive else source_dir.glob("*")
    for path in pattern_iter:
        if path.is_file():
            handler._handle_source_file(path)


def start_whatsapp_ingestion(settings: Settings) -> None:
    cfg = settings.whatsapp_ingestion
    if not cfg.enabled:
        return

    source_dir = cfg.source_dir
    if not source_dir:
        logger.warning("WhatsApp ingestion habilitado, mas source_dir não configurado.")
        return
    if not source_dir.exists():
        logger.warning("Pasta de origem do WhatsApp não existe: %s", source_dir)
        return

    handler = WhatsAppIngestionHandler(settings)
    observer = Observer()
    observer.schedule(handler, str(source_dir), recursive=cfg.recursive)

    logger.info("Watcher do WhatsApp Desktop iniciado para: %s", source_dir)
    observer.start()

    if cfg.startup_scan:
        threading.Thread(target=_startup_scan, args=(settings, handler), daemon=True).start()

