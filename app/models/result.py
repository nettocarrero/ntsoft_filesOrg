from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional

from .document import DocumentInfo
from .enums import ProcessingStatus


@dataclass
class ClassificationResult:
    store_scores: Dict[str, int]
    suggested_store: Optional[str]
    doc_type_scores: Dict[str, int]
    suggested_doc_type: str
    confidence: float
    sent_to_review: bool
    reason: str


@dataclass
class ProcessingResult:
    document: DocumentInfo
    status: ProcessingStatus
    error_message: Optional[str] = None


@dataclass
class ExecutionReport:
    results: List[ProcessingResult] = field(default_factory=list)

    @property
    def total_files(self) -> int:
        return len(self.results)

    @property
    def total_from_zip(self) -> int:
        return sum(
            1
            for r in self.results
            if r.document.came_from_zip
            or (r.document.came_from_archive and r.document.archive_type == "zip")
        )

    @property
    def total_from_archives(self) -> int:
        return sum(1 for r in self.results if r.document.came_from_archive)

    @property
    def total_from_rar(self) -> int:
        return sum(
            1
            for r in self.results
            if r.document.came_from_archive and r.document.archive_type == "rar"
        )

    @property
    def total_review(self) -> int:
        return sum(1 for r in self.results if r.document.sent_to_review)

    @property
    def total_errors(self) -> int:
        return sum(1 for r in self.results if r.status == ProcessingStatus.ERROR)

    @property
    def total_classified_automatic(self) -> int:
        return sum(
            1
            for r in self.results
            if r.status == ProcessingStatus.SUCCESS
            and not r.document.sent_to_review
        )

    @property
    def total_with_cnpj(self) -> int:
        return sum(
            1
            for r in self.results
            if r.status == ProcessingStatus.SUCCESS and r.document.detected_cnpjs
        )

