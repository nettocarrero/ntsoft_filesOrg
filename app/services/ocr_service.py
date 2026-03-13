from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple
import logging

from pdf2image import convert_from_path
import pytesseract

from app.config import OCRConfig


logger = logging.getLogger(__name__)


def configure_tesseract(ocr_cfg: OCRConfig) -> None:
    if ocr_cfg.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = ocr_cfg.tesseract_cmd


def extract_text_with_ocr(pdf_path: Path, ocr_cfg: OCRConfig) -> Tuple[str, Dict]:
    """
    Aplica OCR em um PDF, retornando (texto, metadados).
    Metadados:
      - pages_processed
      - ocr_engine
      - text_length
      - success
    """
    configure_tesseract(ocr_cfg)

    metadata: Dict[str, object] = {
        "pages_processed": 0,
        "ocr_engine": "tesseract",
        "text_length": 0,
        "success": False,
    }

    try:
        max_pages = ocr_cfg.max_pages
        logger.info("Iniciando OCR para arquivo: %s", pdf_path)
        images = convert_from_path(
            str(pdf_path),
            dpi=ocr_cfg.dpi,
            first_page=1,
            last_page=max_pages,
        )
        texts = []
        for idx, img in enumerate(images, start=1):
            text = pytesseract.image_to_string(img, lang=ocr_cfg.language)
            texts.append(text)
        full_text = "\n".join(texts).strip()

        metadata["pages_processed"] = len(images)
        metadata["text_length"] = len(full_text)
        metadata["success"] = len(full_text) > 0

        logger.info(
            "OCR concluído para %s: %d páginas, %d caracteres.",
            pdf_path,
            metadata["pages_processed"],
            metadata["text_length"],
        )
        return full_text, metadata
    except Exception as exc:
        logger.error("OCR falhou para o arquivo %s: %s", pdf_path, exc)
        metadata["success"] = False
        metadata["error"] = str(exc)
        return "", metadata

