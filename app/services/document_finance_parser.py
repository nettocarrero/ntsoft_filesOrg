"""
Extração de informações financeiras de documentos de pagamento (boletos, guias, DARF, etc.).
Retorna data de vencimento e valor para uso em painel financeiro.
Inclui gravação/leitura do arquivo .meta.json ao lado do PDF.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# Palavras-chave para data de vencimento (case insensitive)
VENCIMENTO_KEYWORDS = [
    r"vencimento",
    r"data\s+de\s+vencimento",
    r"vcto\.?",
    r"vencto\.?",
    r"pagar\s+at[eé]",
    r"validade",
    r"data\s+de\s+pagamento",
    r"vencimento\s+do\s+boleto",
]

# Padrões de data: dd/mm/yyyy ou dd-mm-yyyy (com possível ruído)
DATE_PATTERNS = [
    re.compile(
        r"(?<!\d)(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2,4})(?!\d)",
        re.IGNORECASE,
    ),
]

# Padrões de valor em reais: exige vírgula e 2 decimais para não capturar anos/dias (2026, 15)
# R$ 1.234,56 ou 1.234,56 ou 1234,56
AMOUNT_PATTERN = re.compile(
    r"(?:R\s*\$\s*)?(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})",
    re.IGNORECASE,
)

# Palavras próximas a valor (priorizar contexto)
VALOR_KEYWORDS = [
    r"valor",
    r"valor\s+total",
    r"total",
    r"documento",
    r"valor\s+do\s+documento",
    r"valor\s+a\s+pagar",
    r"valor\s+do\s+boleto",
    r"valor\s+documento",
]

# Padrão aproximado de linha digitável de boleto:
# 5 blocos de números com separadores opcionais (espaço, ponto, hífen)
LINHA_DIGITAVEL_PATTERN = re.compile(
    # Padrão mais tolerante: pelo menos ~40 dígitos agrupados em blocos, aceitando espaços/pontos/hífens
    r"(?:\d[\s\.\-]?){40,60}"
)

# Palavras-chave fortemente associadas a boletos
BOLETO_STRONG_KEYWORDS = [
    "recibo do pagador",
    "beneficiario",
    "pagador",
    "nosso numero",
    "agencia",
    "codigo do beneficiario",
    "valor documento",
    "vencimento",
    "autenticacao mecanica",
    "carteira",
    "linha digitavel",
    "boleto bancario",
]

# Nomes de bancos comuns (normalizados)
BOLETO_BANK_KEYWORDS = [
    "bradesco",
    "banco do brasil",
    "caixa economica",
    "caixa economica federal",
    "itau",
    "santander",
    "sicoob",
    "sicredi",
]


def detect_boleto_signals(text: str) -> Dict[str, Any]:
    """
    Detecta sinais fortes de que o documento é um boleto bancário com base no texto.
    Usa:
    - presença de linha digitável
    - palavras-chave clássicas de boleto
    - nomes de bancos típicos
    Retorna um dict com flags e score simples.
    """
    if not text:
        return {"is_boleto": False, "score": 0, "has_linha_digitavel": False}

    text_norm = _normalize_whitespace(text).lower()
    score = 0

    has_linha_digitavel = LINHA_DIGITAVEL_PATTERN.search(text_norm) is not None
    if has_linha_digitavel:
        score += 5  # linha digitável é evidência muito forte

    # Palavras-chave fortes de boleto
    for kw in BOLETO_STRONG_KEYWORDS:
        if kw in text_norm:
            score += 1

    # A própria palavra "boleto" (ex.: "Boleto Pix") é um sinal forte
    if "boleto" in text_norm:
        score += 3

    # Nomes de bancos
    for bank in BOLETO_BANK_KEYWORDS:
        if bank in text_norm:
            score += 1

    return {
        "is_boleto": score >= 4,
        "score": score,
        "has_linha_digitavel": has_linha_digitavel,
    }


def _normalize_whitespace(text: str) -> str:
    """Substitui quebras de linha e múltiplos espaços por espaço único."""
    return " ".join(text.split())


def _parse_br_date(match: re.Match) -> Optional[str]:
    """Converte grupo de captura dd, mm, yyyy em ISO YYYY-MM-DD."""
    try:
        d, m, y = match.group(1), match.group(2), match.group(3)
        year = int(y)
        if year < 100:
            year += 2000 if year < 50 else 1900
        month = int(m)
        day = int(d)
        if 1 <= month <= 12 and 1 <= day <= 31:
            dt = datetime(year, month, day)
            return dt.strftime("%Y-%m-%d")
    except (ValueError, IndexError):
        pass
    return None


def _find_due_date(text: str) -> Tuple[Optional[str], str]:
    """
    Encontra data de vencimento no texto.
    Prioriza datas próximas a palavras-chave de vencimento.
    Retorna (data_iso, "high"|"medium"|"low").
    """
    text_norm = _normalize_whitespace(text)
    text_lower = text_norm.lower()
    candidates: List[Tuple[int, str]] = []  # (pos_keyword_nearest, date_iso)

    for pattern in DATE_PATTERNS:
        for m in pattern.finditer(text_norm):
            iso = _parse_br_date(m)
            if not iso:
                continue
            start = m.start()
            # Distância mínima até alguma keyword; priorizar data que vem *após* a keyword (ex.: "Vencimento: 20/03/2026")
            min_dist = len(text_norm) + 1
            for kw in VENCIMENTO_KEYWORDS:
                for km in re.finditer(kw, text_lower, re.IGNORECASE):
                    kw_end = km.end()
                    dist = abs(km.start() - start)
                    # Data antes da keyword (ex.: "01/02/2025. Vencimento") recebe penalidade
                    if start < kw_end:
                        dist += 10000
                    if dist < min_dist:
                        min_dist = dist
            candidates.append((min_dist, iso))

    if not candidates:
        # Fallback: primeira data válida no texto (baixa confiança)
        for pattern in DATE_PATTERNS:
            m = pattern.search(text_norm)
            if m:
                iso = _parse_br_date(m)
                if iso:
                    return (iso, "low")
        return (None, "low")

    candidates.sort(key=lambda x: x[0])
    best_dist, best_date = candidates[0]
    if best_dist <= 80:
        confidence = "high"
    elif best_dist <= 200:
        confidence = "medium"
    else:
        confidence = "low"
    return (best_date, confidence)


def _parse_amount_str(s: str) -> Optional[float]:
    """Converte string brasileira (1.234,56) em float."""
    s = s.strip().replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _find_amount(text: str) -> Tuple[Optional[float], str]:
    """
    Encontra valor monetário no texto.
    Prioriza valores próximos a palavras como "valor", "total", "documento".
    Retorna (valor_float, "high"|"medium"|"low").
    """
    text_norm = _normalize_whitespace(text)
    text_lower = text_norm.lower()
    candidates: List[Tuple[int, float]] = []  # (min_dist_to_keyword, value)

    for m in AMOUNT_PATTERN.finditer(text_norm):
        raw = m.group(1)
        value = _parse_amount_str(raw)
        if value is None or value <= 0 or value > 1e10:
            continue
        start = m.start()
        min_dist = len(text_norm) + 1
        for kw in VALOR_KEYWORDS:
            for km in re.finditer(kw, text_lower, re.IGNORECASE):
                dist = abs(km.start() - start)
                if dist < min_dist:
                    min_dist = dist
        candidates.append((min_dist, value))

    if not candidates:
        return (None, "low")

    candidates.sort(key=lambda x: x[0])
    best_dist, best_value = candidates[0]
    if best_dist <= 60:
        confidence = "high"
    elif best_dist <= 150:
        confidence = "medium"
    else:
        confidence = "low"
    return (best_value, confidence)


def extract_payment_info(text: str) -> Dict[str, Any]:
    """
    Extrai data de vencimento e valor de um texto de documento de pagamento.

    Retorno:
        {
          "due_date": "YYYY-MM-DD" ou None,
          "amount": float ou None,
          "confidence": "high" | "medium" | "low"
        }
    A confiança é a pior entre as duas extrações (data e valor); se só uma for encontrada,
    reflete a confiança dessa.
    """
    if not text or not text.strip():
        return {
            "due_date": None,
            "amount": None,
            "confidence": "low",
            "is_boleto": False,
            "boleto_score": 0,
            "has_linha_digitavel": False,
        }

    boleto_info = detect_boleto_signals(text)
    due_date, conf_date = _find_due_date(text)
    amount, conf_amount = _find_amount(text)

    order = {"high": 3, "medium": 2, "low": 1}
    if due_date is not None and amount is not None:
        confidence = "high" if min(order[conf_date], order[conf_amount]) >= 2 else "medium"
        if order[conf_date] == 1 or order[conf_amount] == 1:
            confidence = "low"
    elif due_date is not None:
        confidence = conf_date
    elif amount is not None:
        confidence = conf_amount
    else:
        confidence = "low"

    return {
        "due_date": due_date,
        "amount": amount,
        "confidence": confidence,
        "is_boleto": boleto_info["is_boleto"],
        "boleto_score": boleto_info["score"],
        "has_linha_digitavel": boleto_info["has_linha_digitavel"],
    }


def _meta_path_for_pdf(pdf_path: Path) -> Path:
    """Caminho do arquivo de metadados: arquivo.pdf -> arquivo.pdf.meta.json."""
    return pdf_path.parent / (pdf_path.name + ".meta.json")


def write_payment_meta_file(
    pdf_path: Path,
    due_date: Optional[str],
    amount: Optional[float],
    extracted: bool,
) -> None:
    """
    Grava arquivo .meta.json ao lado do PDF com tipo, due_date, amount e extracted.
    due_date em formato YYYY-MM-DD ou None; amount como float ou None.
    """
    meta = {
        "type": "pagamento",
        "due_date": due_date,
        "amount": amount,
        "extracted": extracted,
    }
    meta_path = _meta_path_for_pdf(pdf_path)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def read_payment_meta_file(file_path: Path) -> Optional[Dict[str, Any]]:
    """
    Lê o arquivo .meta.json correspondente ao arquivo (ex.: arquivo.pdf -> arquivo.pdf.meta.json).
    Retorna dict com due_date, amount (e type, extracted) ou None se não existir/inválido.
    """
    meta_path = file_path.parent / (file_path.name + ".meta.json")
    if not meta_path.exists() or not meta_path.is_file():
        return None
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return None
        return data
    except (OSError, json.JSONDecodeError):
        return None
