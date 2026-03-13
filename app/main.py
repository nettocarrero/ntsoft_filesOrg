from __future__ import annotations

import argparse
import logging
import shutil
from pathlib import Path
from typing import Iterable, List, Callable

from app.config import Settings, load_settings
from app.logger import setup_logging
from app.models import DocumentInfo, ProcessingResult
from app.models.enums import ProcessingStatus
from app.services import (
    scan_input_files,
    extract_zip,
    extract_rar,
    extract_pdf_text,
    extract_text_with_ocr,
    classify_document,
    organize_document,
    generate_reports,
)
from app.services.whatsapp_ingestion_service import start_whatsapp_ingestion
from app.services.filter_service import should_ignore_document
from app.utils.file_utils import is_pdf, is_zip, is_rar


logger = logging.getLogger(__name__)


def process() -> None:
    """
    Modo pontual: processa todos os arquivos atualmente presentes em input/.
    """
    setup_logging()
    settings = load_settings()

    logger.info("Iniciando processamento de arquivos (modo pontual).")

    input_files = scan_input_files(settings.paths.input_dir)
    logger.info("Foram encontrados %d arquivos na pasta de entrada.", len(input_files))
    for path in input_files:
        if is_zip(path):
            logger.info("ZIP detectado na pasta de entrada: %s", path)
        elif is_rar(path):
            logger.info("RAR detectado na pasta de entrada: %s", path)
        elif is_pdf(path):
            logger.info("PDF detectado na pasta de entrada: %s", path)

    results = process_input_files(input_files, settings)
    _print_summary(results)


def process_input_files(paths: Iterable[Path], settings: Settings) -> List[ProcessingResult]:
    """
    Processa uma coleção de arquivos de entrada (PDF, ZIP, RAR),
    reutilizável pelo modo pontual e pelo watcher.
    """
    results: List[ProcessingResult] = []

    for path in paths:
        if is_zip(path):
            logger.info("Processando ZIP: %s", path)
            per_file_results = _process_zip(path, settings)
        elif is_rar(path):
            logger.info("Processando RAR: %s", path)
            per_file_results = _process_rar(path, settings)
        elif is_pdf(path):
            logger.info("Processando PDF: %s", path)
            per_file_results = [
                _process_pdf(
                    path,
                    settings,
                    came_from_archive=False,
                    archive_type=None,
                )
            ]
        else:
            logger.info("Arquivo ignorado por extensão não suportada: %s", path)
            per_file_results = []

        results.extend(per_file_results)
        _handle_processed_input_file(path, per_file_results, settings)

    generate_reports(settings.paths.reports_dir, results)
    return results


def _handle_processed_input_file(
    original_path: Path,
    results: List[ProcessingResult],
    settings: Settings,
) -> None:
    """
    Aplica a política de pós-processamento configurada (keep/move/delete)
    para arquivos de entrada que foram processados sem erros.
    """
    action = settings.processed_input.action
    if action not in {"keep", "move", "delete"}:
        logger.warning("Ação de pós-processamento desconhecida: %s", action)
        return

    if any(r.status == ProcessingStatus.ERROR for r in results):
        logger.info("Mantendo arquivo em input por ter ocorrido erro: %s", original_path)
        return

    if action == "keep":
        return

    try:
        if action == "move":
            from datetime import datetime

            today_str = datetime.now().strftime("%Y-%m-%d")
            dest_dir = settings.processed_input.processed_dir / today_str
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_path = dest_dir / original_path.name
            logger.info("Movendo arquivo processado para: %s", dest_path)
            shutil.move(str(original_path), str(dest_path))
        elif action == "delete":
            logger.info("Removendo arquivo de entrada processado: %s", original_path)
            original_path.unlink(missing_ok=True)
    except Exception as exc:
        logger.error(
            "Falha ao aplicar ação '%s' para arquivo de entrada %s: %s",
            action,
            original_path,
            exc,
        )


def _process_zip(zip_path: Path, settings: Settings) -> List[ProcessingResult]:
    results: List[ProcessingResult] = []
    try:
        logger.info("Extraindo ZIP: %s", zip_path)
        extracted_files = extract_zip(zip_path, settings.paths.temp_dir)
        logger.info(
            "ZIP %s extraído para %s com %d arquivos.",
            zip_path,
            settings.paths.temp_dir,
            len(extracted_files),
        )
        pdf_files = [f for f in extracted_files if is_pdf(f)]
        logger.info(
            "Foram encontrados %d PDFs dentro do ZIP %s.",
            len(pdf_files),
            zip_path,
        )
        for f in pdf_files:
            logger.info("Processando PDF extraído de ZIP: %s", f)
            results.append(
                _process_pdf(
                    f,
                    settings,
                    came_from_archive=True,
                    archive_type="zip",
                    archive_root=zip_path,
                )
            )
    except Exception as exc:
        logger.error("Erro ao processar ZIP %s: %s", zip_path, exc)
        doc = DocumentInfo(original_path=zip_path, came_from_zip=False)
        results.append(
            ProcessingResult(
                document=doc,
                status=ProcessingStatus.ERROR,
                error_message=str(exc),
            )
        )
    return results


def _process_rar(rar_path: Path, settings: Settings) -> List[ProcessingResult]:
    results: List[ProcessingResult] = []
    try:
        logger.info("Extraindo RAR: %s", rar_path)
        extracted_files = extract_rar(rar_path, settings.paths.temp_dir)
        logger.info(
            "RAR %s extraído para %s com %d arquivos.",
            rar_path,
            settings.paths.temp_dir,
            len(extracted_files),
        )
        pdf_files = [f for f in extracted_files if is_pdf(f)]
        logger.info(
            "Foram encontrados %d PDFs dentro do RAR %s.",
            len(pdf_files),
            rar_path,
        )
        for f in pdf_files:
            logger.info("Processando PDF extraído de RAR: %s", f)
            results.append(
                _process_pdf(
                    f,
                    settings,
                    came_from_archive=True,
                    archive_type="rar",
                    archive_root=rar_path,
                )
            )
    except Exception as exc:
        logger.error("Erro ao processar RAR %s: %s", rar_path, exc)
        doc = DocumentInfo(original_path=rar_path)
        doc.came_from_archive = True
        doc.archive_type = "rar"
        doc.archive_root = rar_path
        results.append(
            ProcessingResult(
                document=doc,
                status=ProcessingStatus.ERROR,
                error_message=str(exc),
            )
        )
    return results


def _process_pdf(
    pdf_path: Path,
    settings: Settings,
    came_from_archive: bool,
    archive_type: str | None,
    archive_root: Path | None = None,
) -> ProcessingResult:
    doc = DocumentInfo(
        original_path=pdf_path,
        came_from_zip=archive_type == "zip",
        zip_root=archive_root if archive_type == "zip" else None,
        came_from_archive=came_from_archive,
        archive_type=archive_type,
        archive_root=archive_root,
        extracted_path=pdf_path if came_from_archive else None,
    )
    try:
        # Extração textual normal
        text, status = extract_pdf_text(pdf_path)
        doc.text = text
        doc.text_status = status
        doc.text_source = "pdf_text" if status == "ok" and text else "none"

        # Acionamento opcional de OCR
        ocr_cfg = settings.ocr
        if ocr_cfg.enabled and (status == "texto_insuficiente" or (text and len(text) < ocr_cfg.min_text_length_trigger)):
            logger.info("Texto insuficiente detectado, iniciando OCR: %s", pdf_path)
            ocr_text, ocr_meta = extract_text_with_ocr(pdf_path, ocr_cfg)
            doc.ocr_used = True
            doc.ocr_metadata = ocr_meta
            if ocr_meta.get("success") and ocr_text:
                logger.info("OCR concluído com sucesso para: %s", pdf_path)
                doc.text = ocr_text
                doc.text_status = "ok"
                doc.text_source = "ocr"
                doc.ocr_success = True
            else:
                logger.warning("OCR não obteve texto útil para: %s", pdf_path)
                doc.ocr_success = False
        else:
            if status == "ok":
                logger.info("OCR ignorado, texto extraído do PDF é suficiente: %s", pdf_path)

        # Regras de ignorar documentos por nome/texto
        ignore, reason = should_ignore_document(doc, settings)
        if ignore:
            logger.info("Documento ignorado por regra de filtro: %s (%s)", pdf_path, reason)
            doc.ignored = True
            doc.decision_reason = reason
            return ProcessingResult(document=doc, status=ProcessingStatus.SUCCESS)

        doc = classify_document(doc, settings)
        doc = organize_document(doc, settings.paths)

        return ProcessingResult(document=doc, status=ProcessingStatus.SUCCESS)
    except Exception as exc:
        logger.error("Erro ao processar PDF %s: %s", pdf_path, exc)
        return ProcessingResult(
            document=doc,
            status=ProcessingStatus.ERROR,
            error_message=str(exc),
        )


def _print_summary(results: List[ProcessingResult]) -> None:
    from app.models import ExecutionReport

    exec_report = ExecutionReport(results=results)

    print("\n=== Resumo da execução ===")
    print(f"Total de arquivos processados: {exec_report.total_files}")
    print(f"Total vindos de arquivos compactados: {exec_report.total_from_archives}")
    print(f"Total vindos de ZIP: {exec_report.total_from_zip}")
    print(f"Total vindos de RAR: {exec_report.total_from_rar}")
    print(f"Total classificados automaticamente: {exec_report.total_classified_automatic}")
    print(f"Total enviados para revisão manual: {exec_report.total_review}")
    print(f"Total de erros: {exec_report.total_errors}")
    print(f"Total de documentos com CNPJ identificado: {exec_report.total_with_cnpj}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Organizador automático de documentos financeiros.")
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Ativa monitoramento contínuo da pasta de entrada.",
    )
    args = parser.parse_args()

    if args.watch:
        setup_logging()
        settings = load_settings()
        from app.services.watcher_service import start_watcher

        logger.info("Iniciando modo watch para pasta: %s", settings.paths.input_dir)
        # inicia ingestão do WhatsApp (observer próprio, não bloqueante)
        start_whatsapp_ingestion(settings)
        # inicia watcher principal da pasta input (bloqueante)
        start_watcher(settings, process_input_files)
    else:
        process()


if __name__ == "__main__":
    main()
