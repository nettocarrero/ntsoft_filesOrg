from __future__ import annotations

import shutil
from pathlib import Path

from app.config import PathsConfig
from app.models import DocumentInfo
from app.models.enums import DocumentType


def _build_output_path(doc: DocumentInfo, paths: PathsConfig) -> Path:
    if doc.sent_to_review or not doc.suggested_store:
        base = paths.review_manual_dir
        store_folder = doc.suggested_store or "desconhecido"
        type_folder = doc.suggested_doc_type.value
    else:
        base = paths.output_dir
        store_folder = doc.suggested_store
        type_folder = doc.suggested_doc_type.value

    return base / store_folder / type_folder / (doc.extracted_path or doc.original_path).name


def organize_document(doc: DocumentInfo, paths: PathsConfig) -> DocumentInfo:
    src = doc.extracted_path or doc.original_path
    destination = _build_output_path(doc, paths)
    destination.parent.mkdir(parents=True, exist_ok=True)

    shutil.copy2(src, destination)
    doc.destination_path = destination
    return doc

