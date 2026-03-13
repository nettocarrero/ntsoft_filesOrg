from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Callable, Iterable, Set, Tuple

from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileMovedEvent
from watchdog.observers import Observer

from app.config import Settings
from app.models import ProcessingResult
from app.utils.file_utils import is_pdf, is_zip, is_rar


logger = logging.getLogger(__name__)


def wait_until_file_is_ready(
    path: Path,
    timeout: int = 30,
    interval: float = 1.0,
) -> bool:
    """
    Aguarda até que o arquivo pareça "estável":
    - tamanho não muda em duas verificações consecutivas.
    Retorna True se o arquivo parece pronto dentro do timeout.
    """
    logger.info("Aguardando arquivo ficar estável: %s", path)
    end_time = time.time() + timeout
    last_size = -1
    stable_count = 0

    while time.time() < end_time:
        if not path.exists():
            stable_count = 0
            last_size = -1
            time.sleep(interval)
            continue

        size = path.stat().st_size
        if size == last_size and size > 0:
            stable_count += 1
            if stable_count >= 2:
                logger.info("Arquivo pronto para processamento: %s", path)
                return True
        else:
            stable_count = 0
            last_size = size

        time.sleep(interval)

    logger.warning("Timeout ao aguardar arquivo ficar estável: %s", path)
    return False


class InputFolderEventHandler(FileSystemEventHandler):
    def __init__(
        self,
        settings: Settings,
        process_fn: Callable[[Iterable[Path], Settings], list[ProcessingResult]],
    ) -> None:
        super().__init__()
        self.settings = settings
        self.process_fn = process_fn
        self._processed_signatures: Set[Tuple[str, int, float]] = set()
        self._lock = threading.Lock()
        self._max_signatures = 1000

    def _is_relevant(self, path: Path) -> bool:
        return is_pdf(path) or is_zip(path) or is_rar(path)

    def _already_processed(self, path: Path) -> bool:
        try:
            st = path.stat()
        except FileNotFoundError:
            return False
        sig = (str(path), st.st_size, st.st_mtime)
        with self._lock:
            if sig in self._processed_signatures:
                return True
            if len(self._processed_signatures) >= self._max_signatures:
                # estratégia simples: limpa o set ao atingir o limite
                self._processed_signatures.clear()
            self._processed_signatures.add(sig)
        return False

    def _handle_path(self, path: Path) -> None:
        if not self._is_relevant(path):
            logger.info("Arquivo ignorado por extensão não suportada: %s", path)
            return

        if not wait_until_file_is_ready(path):
            logger.warning("Arquivo não ficou pronto a tempo, ignorando por agora: %s", path)
            return

        if self._already_processed(path):
            logger.info("Arquivo já processado recentemente, ignorando: %s", path)
            return

        try:
            self.process_fn([path], self.settings)
        except Exception as exc:
            logger.error("Erro ao processar arquivo disparado pelo watcher %s: %s", path, exc)

    def on_created(self, event: FileCreatedEvent) -> None:
        if event.is_directory:
            return
        path = Path(event.src_path)
        logger.info("Novo arquivo detectado: %s", path)
        threading.Thread(target=self._handle_path, args=(path,), daemon=True).start()

    def on_moved(self, event: FileMovedEvent) -> None:
        if event.is_directory:
            return
        dest = Path(event.dest_path)
        logger.info("Arquivo movido para a pasta de entrada: %s", dest)
        threading.Thread(target=self._handle_path, args=(dest,), daemon=True).start()


def start_watcher(
    settings: Settings,
    process_fn: Callable[[Iterable[Path], Settings], list[ProcessingResult]],
) -> None:
    input_dir = settings.paths.input_dir
    input_dir.mkdir(parents=True, exist_ok=True)

    event_handler = InputFolderEventHandler(settings, process_fn)
    observer = Observer()
    observer.schedule(event_handler, str(input_dir), recursive=False)

    logger.info("Modo watch iniciado para pasta input: %s", input_dir)
    observer.start()

    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        logger.info("Encerrando modo watch por interrupção do usuário.")
    finally:
        observer.stop()
        observer.join()

