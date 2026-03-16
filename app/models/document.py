from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional, Dict, Any, List

from .enums import DocumentType


@dataclass
class DocumentInfo:
    original_path: Path
    # Compatibilidade legada (ZIP). Preferir campos genéricos abaixo.
    came_from_zip: bool = False
    zip_root: Optional[Path] = None
    # Origem genérica de arquivo compactado
    came_from_archive: bool = False
    archive_type: Optional[str] = None  # "zip", "rar", etc.
    archive_root: Optional[Path] = None
    extracted_path: Optional[Path] = None
    text: Optional[str] = None
    text_status: str = "nao_processado"  # "ok" | "texto_insuficiente" | "erro"
    text_source: str = "none"  # "pdf_text" | "ocr" | "none"
    ocr_used: bool = False
    ocr_success: bool = False
    ocr_metadata: Dict[str, Any] = field(default_factory=dict)
    detected_cnpjs: List[str] = field(default_factory=list)
    # Scores agregados
    store_scores: Dict[str, int] = field(default_factory=dict)
    doc_type_scores: Dict[DocumentType, int] = field(default_factory=dict)
    suggested_store: Optional[str] = None
    suggested_doc_type: DocumentType = DocumentType.DESCONHECIDO
    # Data do documento (para organização ano/mês); se None, usa data atual
    document_date: Optional[date] = None
    # Confianças separadas
    store_confidence: float = 0.0
    type_confidence: float = 0.0
    overall_confidence: float = 0.0
    # Evidência forte (por exemplo, CNPJ)
    has_strong_store_evidence: bool = False
    strong_evidence_type: Optional[str] = None
    # Detalhes de evidências usadas na decisão
    score_details: Dict[str, Any] = field(default_factory=dict)
    # Resultado operacional
    destination_path: Optional[Path] = None
    sent_to_review: bool = False
    decision_reason: str = ""
    decision_explanation: str = ""
    ignored: bool = False

