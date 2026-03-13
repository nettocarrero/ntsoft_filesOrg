from __future__ import annotations

from pathlib import Path
from typing import List
import logging

import rarfile

from app.utils.path_utils import sanitize_archive_member_path, sanitize_windows_path_part


logger = logging.getLogger(__name__)


def _detect_root_folder_name(rf: rarfile.RarFile, rar_path: Path) -> str | None:
    """
    Se todos os membros estiverem sob uma mesma pasta raiz, retorna o nome dessa pasta.
    Caso contrário, retorna None.
    """
    root_candidates: set[str] = set()
    for info in rf.infolist():
        name = info.filename
        if not name:
            continue
        # normaliza separadores
        parts = name.replace("\\", "/").split("/")
        if parts[0] and parts[0] not in (".", ".."):
            root_candidates.add(parts[0])
    if len(root_candidates) == 1:
        return next(iter(root_candidates))
    return None


def extract_rar(rar_path: Path, temp_dir: Path) -> List[Path]:
    """
    Extrai o RAR para uma subpasta em temp, preservando a estrutura interna
    de forma sanitizada para Windows.
    Retorna a lista de todos os arquivos extraídos.
    """
    target_dir = temp_dir / rar_path.stem
    target_dir.mkdir(parents=True, exist_ok=True)

    extracted_files: List[Path] = []
    extracted_count = 0
    skipped_count = 0

    try:
        logger.info("Iniciando extração de RAR com rarfile: %s", rar_path)
        with rarfile.RarFile(rar_path) as rf:
            root_in_archive = _detect_root_folder_name(rf, rar_path)
            rar_stem_clean = sanitize_windows_path_part(rar_path.stem)
            drop_root = root_in_archive and sanitize_windows_path_part(root_in_archive) == rar_stem_clean

            for info in rf.infolist():
                orig_name = info.filename
                if not orig_name or orig_name.endswith("/"):
                    # Diretório ou entrada vazia
                    continue

                # Remove pasta raiz duplicada, se aplicável
                rel_name = orig_name
                if drop_root:
                    rel_name = rel_name.replace("\\", "/")
                    if rel_name.startswith(root_in_archive + "/"):
                        rel_name = rel_name[len(root_in_archive) + 1 :]

                sanitized_rel_path = sanitize_archive_member_path(rel_name)
                logger.info(
                    "Membro RAR sanitizado: '%s' -> '%s'",
                    orig_name,
                    sanitized_rel_path.as_posix(),
                )

                dest_path = (target_dir / sanitized_rel_path).resolve()
                # Segurança: garantir que o destino está dentro de target_dir
                try:
                    target_dir_resolved = target_dir.resolve()
                except FileNotFoundError:
                    target_dir_resolved = target_dir

                if target_dir_resolved not in dest_path.parents and dest_path != target_dir_resolved:
                    logger.warning(
                        "Ignorando membro RAR por tentativa de path traversal: '%s' -> '%s'",
                        orig_name,
                        dest_path,
                    )
                    skipped_count += 1
                    continue

                dest_path.parent.mkdir(parents=True, exist_ok=True)

                try:
                    with rf.open(info) as src, open(dest_path, "wb") as dst:
                        dst.write(src.read())
                    logger.info("Arquivo extraído com sucesso: %s", dest_path)
                    extracted_files.append(dest_path)
                    extracted_count += 1
                except Exception as exc:
                    logger.error(
                        "Erro ao extrair membro '%s' para '%s': %s",
                        orig_name,
                        dest_path,
                        exc,
                    )
                    skipped_count += 1

    except rarfile.RarCannotExec as exc:
        msg = (
            "Falha ao executar extrator de RAR. "
            "Certifique-se de que um utilitário como 'unrar', 'rar' ou 'bsdtar' "
            "está instalado e acessível no PATH do sistema. "
            f"Detalhes: {exc}"
        )
        logger.error(msg)
        raise RuntimeError(msg) from exc
    except Exception as exc:
        msg = f"Erro ao extrair arquivo RAR {rar_path}: {exc}"
        logger.error(msg)
        raise RuntimeError(msg) from exc

    logger.info(
        "Extração de RAR concluída: %d arquivos extraídos, %d membros ignorados.",
        extracted_count,
        skipped_count,
    )

    return extracted_files

