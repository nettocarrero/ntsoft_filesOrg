from __future__ import annotations

from enum import Enum, auto


class DocumentType(str, Enum):
    BOLETO = "boleto"
    NOTA_FISCAL = "nota_fiscal"
    NOTA_SERVICO = "nota_servico"
    TAXA = "taxa"
    COMPROVANTE = "comprovante"
    DESCONHECIDO = "desconhecido"


class ProcessingStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    REVIEW_REQUIRED = "review_required"


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

