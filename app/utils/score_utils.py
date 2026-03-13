from __future__ import annotations

from typing import Dict, Tuple, Optional


def pick_best_with_margin(
    scores: Dict[str, int], min_score: int, margin: int
) -> Tuple[Optional[str], Dict[str, int]]:
    """
    Retorna (melhor_chave_ou_None, scores_ordenados_por_score_desc).
    Aplica limiar mínimo e margem entre primeiro e segundo colocado.
    """
    if not scores:
        return None, {}

    ordered = dict(sorted(scores.items(), key=lambda kv: kv[1], reverse=True))
    items = list(ordered.items())

    best_key, best_score = items[0]
    if best_score < min_score:
        return None, ordered

    if len(items) > 1:
        second_score = items[1][1]
        if best_score - second_score < margin:
            return None, ordered

    return best_key, ordered


def compute_confidence_component(
    scores: Dict[str, int],
    best_key: Optional[str],
    evidence_count: int,
    min_score: int,
) -> float:
    """
    Calcula uma confiança normalizada em [0, 1] para um conjunto de scores.

    - Usa o melhor score relativo ao min_score configurado.
    - Considera a quantidade de evidências (ocorrências) usadas.
    - Mantida simples para facilitar calibração futura.
    """
    if not scores or not best_key:
        return 0.0

    best_score = scores.get(best_key, 0)
    if best_score <= 0:
        return 0.0

    score_factor = min(1.0, best_score / max(min_score, 1))
    evidence_factor = min(1.0, evidence_count / 3)  # após 3 evidências, saturamos

    confidence = 0.7 * score_factor + 0.3 * evidence_factor
    return round(confidence, 3)

