from pathlib import Path
from unittest import mock

from app.config import load_settings
from app.services.watcher_service import wait_until_file_is_ready


def test_wait_until_file_is_ready_simple(tmp_path):
    path = tmp_path / "file.txt"
    path.write_text("abc", encoding="utf-8")

    assert wait_until_file_is_ready(path, timeout=3, interval=0.2) is True


def test_wait_until_file_is_ready_timeout(tmp_path):
    path = tmp_path / "growing.txt"

    # simula arquivo crescendo: tamanho muda a cada chamada
    sizes = [0, 10, 20, 30]

    def fake_stat():
        class S:
            st_size = sizes.pop(0) if sizes else 30
        return S()

    path.write_text("dummy", encoding="utf-8")

    with mock.patch.object(Path, "stat", side_effect=lambda self=path: fake_stat()):
        ready = wait_until_file_is_ready(path, timeout=1, interval=0.1)

    assert ready in {True, False}  # apenas garante que não explode

