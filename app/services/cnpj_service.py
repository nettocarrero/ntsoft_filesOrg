from __future__ import annotations

import re
from typing import List, Optional, Dict, Any, Tuple


_CNPJ_PATTERN = re.compile(r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}")

_OCR_CHAR_MAP = {
    "o": "0",
    "O": "0",
    "i": "1",
    "I": "1",
    "l": "1",
    "L": "1",
    "b": "8",
    "B": "8",
    "s": "5",
    "S": "5",
    "z": "2",
    "Z": "2",
}


def normalize_ocr_cnpj_candidate(text: str) -> str:
    """
    Normaliza um candidato a CNPJ vindo de OCR:
    - converte caracteres comumente confundidos (O->0, I/l->1, B->8, S->5, Z->2)
    - remove tudo que não seja dígito
    - retorna string com 14 dígitos ou string vazia
    """
    if not text:
        return ""
    mapped = []
    for ch in text:
        if ch.isdigit():
            mapped.append(ch)
        elif ch in _OCR_CHAR_MAP:
            mapped.append(_OCR_CHAR_MAP[ch])
        # outros caracteres são ignorados
    digits = "".join(mapped)
    return digits if len(digits) == 14 else ""


def extract_cnpj_candidates_from_noisy_text(text: str) -> List[str]:
    """
    Extrai candidatos a CNPJ de texto ruidoso (OCR).
    Procura por sequências de caracteres que possam conter CNPJ e aplica
    normalize_ocr_cnpj_candidate.
    """
    if not text:
        return []

    # candidatos com letras, dígitos e pontuação típica de CNPJ
    pattern = re.compile(r"[0-9A-Za-z\./\- ]{14,24}")
    candidates: List[str] = []
    for m in pattern.finditer(text):
        raw = m.group(0)
        normalized = normalize_ocr_cnpj_candidate(raw)
        if normalized:
            candidates.append(normalized)

    # remover duplicados preservando ordem
    seen = set()
    unique: List[str] = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique.append(c)

    return unique


def extract_cnpjs_with_ocr_robust(text: str, is_ocr: bool = False) -> Tuple[List[str], Dict[str, Any]]:
    """
    Extrai CNPJs usando:
    - modo normal (regex + sequências de 14 dígitos)
    - modo robusto para OCR (normalização de caracteres confusos)

    Retorna (lista_de_cnpjs, metadados), onde metadados inclui:
    - detection_mode: "normal" | "ocr_robust" | "mixed" | "none"
    - normal_matches
    - robust_matches
    - normalized_candidates
    """
    meta: Dict[str, Any] = {
        "detection_mode": "none",
        "normal_matches": [],
        "robust_matches": [],
        "normalized_candidates": [],
    }

    if not text:
        return [], meta

    normalized: List[str] = []

    # camada normal
    matches = _CNPJ_PATTERN.findall(text)
    for raw in matches:
        digits = re.sub(r"\D", "", raw)
        if len(digits) == 14:
            normalized.append(digits)
    pure_matches = re.findall(r"\b\d{14}\b", text)
    for raw in pure_matches:
        digits = re.sub(r"\D", "", raw)
        if len(digits) == 14:
            normalized.append(digits)

    meta["normal_matches"] = list(normalized)

    # camada robusta para OCR:
    # se o texto veio de OCR ou se não encontramos nada na camada normal
    robust: List[str] = []
    if is_ocr or not normalized:
        robust = extract_cnpj_candidates_from_noisy_text(text)
        meta["robust_matches"] = robust
        normalized.extend(robust)

    # remover duplicados preservando ordem
    seen = set()
    unique: List[str] = []
    for c in normalized:
        if c not in seen:
            seen.add(c)
            unique.append(c)

    meta["normalized_candidates"] = unique
    if unique and meta["normal_matches"] and meta["robust_matches"]:
        meta["detection_mode"] = "mixed"
    elif unique and meta["robust_matches"]:
        meta["detection_mode"] = "ocr_robust"
    elif unique:
        meta["detection_mode"] = "normal"

    return unique, meta


def extract_cnpjs_from_text(text: str) -> List[str]:
    """
    Função legada: mantém comportamento anterior (modo normal apenas).
    """
    cnpjs, _ = extract_cnpjs_with_ocr_robust(text, is_ocr=False)
    return cnpjs


def build_cnpj_index(aliases_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Constrói índice cnpj -> store_code a partir da configuração de aliases.
    """
    index: Dict[str, str] = {}
    stores = aliases_data.get("stores", {})
    for store_code, info in stores.items():
        for cnpj in info.get("cnpjs", []):
            digits = re.sub(r"\D", "", str(cnpj))
            if len(digits) == 14:
                index[digits] = store_code
    return index


def match_cnpj_to_store(cnpj: str, aliases_data: Dict[str, Any]) -> Optional[str]:
    """
    Retorna o código da loja correspondente ao CNPJ, se existir.
    """
    digits = re.sub(r"\D", "", str(cnpj))
    if len(digits) != 14:
        return None

    index = build_cnpj_index(aliases_data)
    return index.get(digits)

