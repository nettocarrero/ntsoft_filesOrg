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

# Palavras-chave que indicam datas que NÃO são vencimento (emissão, processamento etc.)
NON_DUE_DATE_KEYWORDS = [
    r"data\s+do\s+documento",
    r"data\s+documento",
    r"data\s+de\s+emiss[aã]o",
    r"emiss[aã]o",
    r"data\s+processamento",
    r"processamento",
]

# Palavras-chave comuns em datas de multa/juros (não são vencimento)
PENALTY_DATE_KEYWORDS = [
    r"a\s+partir\s+de",
    r"mora",
    r"multa",
    r"juros",
    r"encargos",
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
    Estratégia:
      1) Tenta achar datas na mesma linha (ou logo abaixo) de palavras como "Vencimento".
      2) Se não encontrar, cai para heurística global baseada em distância.
    Retorna (data_iso, "high"|"medium"|"low").
    """
    # 1) Busca linha a linha: datas próximas da palavra "vencimento"
    lines = text.splitlines()
    for idx, raw_line in enumerate(lines):
        line = raw_line.strip()
        lower = line.lower()
        if any(re.search(kw, lower, re.IGNORECASE) for kw in VENCIMENTO_KEYWORDS):
            # procura data na mesma linha
            for pattern in DATE_PATTERNS:
                m = pattern.search(line)
                if m:
                    iso = _parse_br_date(m)
                    if iso:
                        return (iso, "high")
            # se não achar, tenta na próxima linha (muitos boletos escrevem "Vencimento" e a data na linha de baixo)
            if idx + 1 < len(lines):
                next_line = lines[idx + 1]
                for pattern in DATE_PATTERNS:
                    m = pattern.search(next_line)
                    if m:
                        iso = _parse_br_date(m)
                        if iso:
                            return (iso, "medium")

    # 2) Heurística global anterior (fallback)
    text_norm = _normalize_whitespace(text)
    text_lower = text_norm.lower()
    candidates: List[Tuple[int, str]] = []  # (pos_keyword_nearest, date_iso)

    for pattern in DATE_PATTERNS:
        for m in pattern.finditer(text_norm):
            iso = _parse_br_date(m)
            if not iso:
                continue
            start = m.start()

            # Ignora datas em janelas de texto claramente ligadas a emissão/processamento
            win_start = max(0, start - 60)
            win_end = min(len(text_lower), start + 60)
            window = text_lower[win_start:win_end]
            if any(re.search(kw, window, re.IGNORECASE) for kw in NON_DUE_DATE_KEYWORDS):
                continue

            # Distância mínima até alguma keyword de vencimento; priorizar data que vem *após* a keyword
            min_dist = len(text_norm) + 1
            for kw in VENCIMENTO_KEYWORDS:
                for km in re.finditer(kw, text_lower, re.IGNORECASE):
                    kw_end = km.end()
                    dist = abs(km.start() - start)
                    # Data antes da keyword recebe penalidade forte
                    if start < kw_end:
                        dist += 10000
                    if dist < min_dist:
                        min_dist = dist
            candidates.append((min_dist, iso))

    if not candidates:
        # Fallback final: primeira data válida no texto (baixa confiança)
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
        confidence = "medium"
    elif best_dist <= 200:
        confidence = "low"
    else:
        confidence = "low"
    return (best_date, confidence)


def _refine_boleto_due_date(
    text: str, current_due: Optional[str], current_conf: str
) -> Tuple[Optional[str], str]:
    """
    Heurística extra para boletos:
    - considera todas as datas válidas que NÃO estejam perto de palavras de emissão/processamento;
    - escolhe a maior data (boleto normalmente tem vencimento após emissão);
    - se não houver data melhor, mantém o resultado atual.
    """
    text_norm = _normalize_whitespace(text)
    text_lower = text_norm.lower()

    # Se já encontramos vencimento com boa confiança (perto de keyword), não substituímos.
    if current_due is not None and current_conf in ("high", "medium"):
        return current_due, current_conf

    all_dates: List[str] = []

    for pattern in DATE_PATTERNS:
        for m in pattern.finditer(text_norm):
            iso = _parse_br_date(m)
            if not iso:
                continue

            start = m.start()
            win_start = max(0, start - 60)
            win_end = min(len(text_lower), start + 60)
            window = text_lower[win_start:win_end]
            if any(re.search(kw, window, re.IGNORECASE) for kw in NON_DUE_DATE_KEYWORDS):
                continue
            # Ignora datas de "mora/multa/juros a partir de ..."
            if any(re.search(kw, window, re.IGNORECASE) for kw in PENALTY_DATE_KEYWORDS):
                continue

            all_dates.append(iso)

    if not all_dates:
        return current_due, current_conf

    latest_date = max(all_dates)  # ISO YYYY-MM-DD permite comparação lexicográfica

    if current_due is None:
        return latest_date, "medium"

    # Se já temos uma data e a maior encontrada é posterior, assumimos que ela é o vencimento.
    if latest_date > current_due:
        # Mantém confiança atual se já for alta, senão pelo menos "medium"
        order = {"low": 1, "medium": 2, "high": 3}
        new_conf = current_conf
        if order.get(current_conf, 1) < order["medium"]:
            new_conf = "medium"
        return latest_date, new_conf

    return current_due, current_conf


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
    # Para boletos, aplicamos uma heurística extra: em geral o vencimento é a MAIOR data do documento.
    if boleto_info["is_boleto"]:
        due_date, conf_date = _refine_boleto_due_date(text, due_date, conf_date)
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


def update_payment_status(
    pdf_path: Path,
    status: str,
    paid_at: Optional[str] = None,
    paid_value: Optional[float] = None,
) -> None:
    """
    Atualiza status de pagamento no .meta.json (ex.: open, paid, ignored).
    Não altera o PDF original.
    """
    meta_path = _meta_path_for_pdf(pdf_path)
    if not meta_path.exists():
        return
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            data = {}
    except (OSError, json.JSONDecodeError):
        data = {}

    data["status"] = status
    if paid_at is not None:
        data["paid_at"] = paid_at
    if paid_value is not None:
        data["paid_value"] = paid_value

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def update_payment_due_date(
    pdf_path: Path,
    due_date: Optional[str],
) -> None:
    """
    Atualiza a data de vencimento no .meta.json (formato YYYY-MM-DD).
    """
    meta_path = _meta_path_for_pdf(pdf_path)
    if not meta_path.exists():
        return
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            data = {}
    except (OSError, json.JSONDecodeError):
        data = {}

    data["due_date"] = due_date

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


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
        "status": "open",
        "paid_at": None,
        "paid_value": None,
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
        # Backwards-compat: se não houver status, considera "open"
        if "status" not in data:
            data["status"] = "open"
        return data
    except (OSError, json.JSONDecodeError):
        return None
