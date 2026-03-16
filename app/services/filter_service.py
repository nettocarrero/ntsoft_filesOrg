from __future__ import annotations

from pathlib import Path
from typing import Tuple

from app.config import Settings
from app.models import DocumentInfo
from app.utils import normalize_text


def should_ignore_document(doc: DocumentInfo, settings: Settings) -> Tuple[bool, str]:
    """
    Aplica regras de ignorar documentos com base em nome de arquivo e texto.
    Retorna (ignorar, motivo).
    """
    # Regras fixas iniciais (podem ser movidas para config futuramente)
    generic_rules = [
        "formulario",
        "baixa de estoque",
        "orcamento",
        "orçamento",
        "devolucao",
        "devolução",
    ]
    text_only_rules = [
        "status do pedido processado",
    ]

    normalized_name = normalize_text((doc.extracted_path or doc.original_path).name)
    if doc.text:
        normalized_text = normalize_text(doc.text)
    else:
        normalized_text = ""

    # Regra específica: boletos emitidos POR nós (saída), onde nosso nome
    # aparece como BENEFICIÁRIO (não como pagador).
    # Ex.: "Nome do Beneficiário  VAREJAO CHOCOBALAS COMERCIAL DE ALIMENTO"
    # Usamos a sequência normalizada "beneficiario varejao chocobalas comercial de alimento"
    # para evitar ignorar documentos em que o nome apareça em outro contexto.
    if normalized_text and "beneficiario varejao chocobalas comercial de alimento" in normalized_text:
        return True, "Ignorado por ser boleto emitido como beneficiário (chocobalas saída)"

    # regras genéricas: se aparecerem no nome OU no texto, ignorar
    for rule in generic_rules:
        norm_rule = normalize_text(rule)
        if norm_rule in normalized_name or (normalized_text and norm_rule in normalized_text):
            return True, f"Ignorado por regra (nome/texto) contendo: '{rule}'"

    # regras específicas só de texto
    for rule in text_only_rules:
        norm_rule = normalize_text(rule)
        if normalized_text and norm_rule in normalized_text:
            return True, f"Ignorado por regra de conteudo: '{rule}'"

    return False, ""

