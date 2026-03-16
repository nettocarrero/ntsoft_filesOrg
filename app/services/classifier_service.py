from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, List

from app.config import Settings
from app.models import DocumentInfo, DocumentType
from app.utils import normalize_text, pick_best_with_margin
from app.utils.score_utils import compute_confidence_component
from app.services.cnpj_service import (
    extract_cnpjs_from_text,
    extract_cnpjs_with_ocr_robust,
    build_cnpj_index,
)
from app.services.document_finance_parser import detect_boleto_signals


def _build_store_alias_index(aliases_cfg: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    """
    Retorna um índice de aliases normalizados -> metadados da loja.
    Ex.: {"ubajara": {"code": "ljUbj", "alias": "ubajara", "kind": "city"}}
    """
    index: Dict[str, Dict[str, str]] = {}
    stores = aliases_cfg.get("stores", {})
    for code, info in stores.items():
        for alias in info.get("aliases", []):
            norm = normalize_text(alias)
            if norm:
                index[norm] = {"code": code, "alias": alias, "kind": "alias"}
        city = info.get("city")
        if city:
            norm_city = normalize_text(city)
            if norm_city:
                index[norm_city] = {"code": code, "alias": city, "kind": "city"}
        for kw in info.get("address_keywords", []):
            norm_kw = normalize_text(kw)
            if norm_kw and norm_kw not in index:
                index[norm_kw] = {"code": code, "alias": kw, "kind": "address"}
    return index


def _score_store_from_path(
    path: Path,
    store_index: Dict[str, Dict[str, str]],
    weight_folder: int,
    weight_filename: int,
    evidence: List[Dict[str, Any]],
) -> Dict[str, int]:
    scores: Dict[str, int] = {}
    parts = list(path.parts)
    norm_parts = [normalize_text(part) for part in parts]

    # Pastas (todos os diretórios intermediários)
    for raw_part, norm_part in zip(parts[:-1], norm_parts[:-1]):
        for key, meta in store_index.items():
            if key and key in norm_part:
                code = meta["code"]
                scores[code] = scores.get(code, 0) + weight_folder
                evidence.append(
                    {
                        "store": code,
                        "alias": meta["alias"],
                        "kind": meta["kind"],
                        "location": "folder",
                        "context": raw_part,
                    }
                )

    # Nome do arquivo
    raw_filename = parts[-1]
    filename_norm = norm_parts[-1]
    for key, meta in store_index.items():
        if key and key in filename_norm:
            code = meta["code"]
            scores[code] = scores.get(code, 0) + weight_filename
            evidence.append(
                {
                    "store": code,
                    "alias": meta["alias"],
                    "kind": meta["kind"],
                    "location": "filename",
                    "context": raw_filename,
                }
            )

    return scores


def _score_store_from_zip(
    zip_root: Path | None,
    store_index: Dict[str, Dict[str, str]],
    weight_zip_name: int,
    evidence: List[Dict[str, Any]],
) -> Dict[str, int]:
    scores: Dict[str, int] = {}
    if not zip_root:
        return scores

    parts = list(zip_root.parts)
    norm_parts = [normalize_text(part) for part in parts]

    for raw_part, norm_part in zip(parts, norm_parts):
        for key, meta in store_index.items():
            if key and key in norm_part:
                code = meta["code"]
                scores[code] = scores.get(code, 0) + weight_zip_name
                evidence.append(
                    {
                        "store": code,
                        "alias": meta["alias"],
                        "kind": meta["kind"],
                        "location": "zip_path",
                        "context": raw_part,
                    }
                )

    return scores


def _score_store_from_text(
    text: str,
    store_index: Dict[str, Dict[str, str]],
    weight_text: int,
    evidence: List[Dict[str, Any]],
) -> Dict[str, int]:
    scores: Dict[str, int] = {}
    norm_text = normalize_text(text)
    for key, meta in store_index.items():
        if key and key in norm_text:
            code = meta["code"]
            scores[code] = scores.get(code, 0) + weight_text
            evidence.append(
                {
                    "store": code,
                    "alias": meta["alias"],
                    "kind": meta["kind"],
                    "location": "text",
                    "context": None,
                }
            )
    return scores


def _merge_scores(*dicts: Dict[str, int]) -> Dict[str, int]:
    result: Dict[str, int] = {}
    for d in dicts:
        for k, v in d.items():
            result[k] = result.get(k, 0) + v
    return result


def _score_doc_type(
    text: str, keywords_cfg: Dict[str, Any], evidence: List[Dict[str, Any]]
) -> Dict[DocumentType, int]:
    scores: Dict[DocumentType, int] = {}
    norm_text = normalize_text(text)
    for type_name, info in keywords_cfg.items():
        dt = (
            DocumentType(type_name)
            if type_name in DocumentType._value2member_map_
            else DocumentType.DESCONHECIDO
        )
        kws = info.get("keywords", [])
        for kw in kws:
            norm_kw = normalize_text(kw)
            if norm_kw and norm_kw in norm_text:
                scores[dt] = scores.get(dt, 0) + 1
                evidence.append(
                    {
                        "doc_type": dt.value,
                        "keyword": kw,
                        "location": "text",
                    }
                )
    return scores


def classify_document(doc: DocumentInfo, settings: Settings) -> DocumentInfo:
    store_index = _build_store_alias_index(settings.aliases)

    store_evidence: List[Dict[str, Any]] = []
    type_evidence: List[Dict[str, Any]] = []
    cnpj_matches: List[Dict[str, Any]] = []

    # 1) Evidência por CNPJ (mais forte)
    cnpj_index = build_cnpj_index(settings.aliases)
    cnpj_scores: Dict[str, int] = {}
    if doc.text:
        is_ocr_text = getattr(doc, "text_source", "") == "ocr"
        detected, cnpj_meta = extract_cnpjs_with_ocr_robust(doc.text, is_ocr=is_ocr_text)
        doc.detected_cnpjs = detected
        for cnpj in detected:
            store_code = cnpj_index.get(cnpj)
            if store_code:
                cnpj_scores[store_code] = cnpj_scores.get(store_code, 0) + 20
                cnpj_matches.append(
                    {
                        "cnpj": cnpj,
                        "store": store_code,
                        "source": "ocr_text" if is_ocr_text else "pdf_text",
                        "detection_mode": cnpj_meta.get("detection_mode"),
                    }
                )

    # 2) Loja: pasta + nome + contexto de ZIP + texto
    weight_folder = settings.scoring.store_weights["folder_match"]
    weight_filename = settings.scoring.store_weights["filename_match"]
    weight_text = settings.scoring.store_weights["text_match"]
    weight_zip_name = settings.scoring.store_weights.get("zip_name_match", 5)

    path_for_scoring = doc.extracted_path or doc.original_path
    path_scores = _score_store_from_path(
        path_for_scoring,
        store_index,
        weight_folder,
        weight_filename,
        store_evidence,
    )
    zip_scores = _score_store_from_zip(
        doc.zip_root,
        store_index,
        weight_zip_name,
        store_evidence,
    )
    text_scores = {}
    if doc.text:
        text_scores = _score_store_from_text(
            doc.text,
            store_index,
            weight_text,
            store_evidence,
        )

    store_scores = _merge_scores(cnpj_scores, path_scores, zip_scores, text_scores)
    best_store, ordered_store_scores = pick_best_with_margin(
        store_scores,
        settings.thresholds.store_min_score,
        settings.thresholds.store_margin,
    )

    # Tipo de documento
    doc_type_scores: Dict[DocumentType, int] = {}
    if doc.text:
        doc_type_scores = _score_doc_type(doc.text, settings.document_keywords, type_evidence)

        # Reforço específico para boletos usando sinais fortes (linha digitável, palavras-chave, bancos)
        boleto_signals = detect_boleto_signals(doc.text)
        if boleto_signals.get("is_boleto"):
            current = doc_type_scores.get(DocumentType.BOLETO, 0)
            # Bônus suficiente para ultrapassar o doc_type_min_score padrão
            doc_type_scores[DocumentType.BOLETO] = current + 6
            type_evidence.append(
                {
                    "doc_type": DocumentType.BOLETO.value,
                    "keyword": f"detected_boleto_signals(score={boleto_signals.get('score')}, linha_digitavel={boleto_signals.get('has_linha_digitavel')})",
                    "location": "text",
                }
            )

    best_doc_type, ordered_doc_type_scores = None, {}
    if doc_type_scores:
        temp = {dt.value: score for dt, score in doc_type_scores.items()}
        best_type_value, ordered_type_scores = pick_best_with_margin(
            {k: v for k, v in temp.items()},
            settings.thresholds.doc_type_min_score,
            settings.thresholds.doc_type_margin,
        )
        best_doc_type = (
            DocumentType(best_type_value)
            if best_type_value
            else DocumentType.DESCONHECIDO
        )
        ordered_doc_type_scores = {
            DocumentType(k): v for k, v in ordered_type_scores.items()
        }
    else:
        best_doc_type = DocumentType.DESCONHECIDO

    # Contagem de evidências por loja/tipo para camada de análise
    store_evidence_for_best = [
        e for e in store_evidence if e.get("store") == best_store
    ] if best_store else []
    type_evidence_for_best = [
        e for e in type_evidence if e.get("doc_type") == best_doc_type.value
    ] if best_doc_type else []

    # Confianças separadas
    store_confidence = compute_confidence_component(
        ordered_store_scores,
        best_store,
        len(store_evidence_for_best),
        settings.thresholds.store_min_score,
    )

    # Evidência forte baseada em CNPJ: pelo menos um CNPJ que aponta
    # para a loja vencedora e sem conflito de CNPJ com outras lojas.
    cnpj_stores = {m["store"] for m in cnpj_matches}
    has_cnpj_conflict = len(cnpj_stores) > 1
    has_cnpj_for_best = best_store is not None and best_store in cnpj_stores
    has_strong_store_evidence = has_cnpj_for_best and not has_cnpj_conflict

    # Se há evidência forte de CNPJ, elevamos a confiança mínima da loja
    if has_strong_store_evidence:
        store_confidence = max(store_confidence, 0.95)

    # Para tipo de documento usamos os scores "brutos"
    raw_type_scores = {dt.value: score for dt, score in doc_type_scores.items()}
    best_type_key = best_doc_type.value if best_doc_type else None
    type_confidence = compute_confidence_component(
        raw_type_scores,
        best_type_key,
        len(type_evidence_for_best),
        settings.thresholds.doc_type_min_score,
    )

    overall_confidence = round(
        (store_confidence + type_confidence) / 2.0, 3
    )

    doc.store_scores = ordered_store_scores
    doc.doc_type_scores = ordered_doc_type_scores
    doc.suggested_store = best_store
    doc.suggested_doc_type = best_doc_type
    doc.store_confidence = store_confidence
    doc.type_confidence = type_confidence
    doc.overall_confidence = overall_confidence
    doc.has_strong_store_evidence = has_strong_store_evidence
    doc.strong_evidence_type = "cnpj_match" if has_strong_store_evidence else None

    # Detalhamento de evidências
    doc.score_details = {
        "matched_store_aliases": store_evidence,
        "matched_store_sources": sorted(
            {e["location"] for e in store_evidence}
        ),
        "matched_type_keywords": type_evidence,
        "matched_type_sources": sorted(
            {e["location"] for e in type_evidence}
        ),
        "cnpj_matches": cnpj_matches,
        "cnpj_detection_mode": cnpj_meta.get("detection_mode") if doc.text else None,
        "cnpj_candidates": cnpj_meta.get("normalized_candidates") if doc.text else [],
        "has_strong_store_evidence": has_strong_store_evidence,
        "strong_evidence_type": "cnpj_match" if has_strong_store_evidence else None,
    }

    # Camada de análise de evidências: evitar classificações frágeis
    fragile_store = best_store is None or len(store_evidence_for_best) <= 1
    fragile_type = (
        best_doc_type is None
        or best_doc_type == DocumentType.DESCONHECIDO
        or len(type_evidence_for_best) == 0
    )

    if best_store is None:
        doc.sent_to_review = True
        doc.decision_reason = "Loja não identificada com confiança suficiente."
    elif has_strong_store_evidence and not has_cnpj_conflict:
        # Evidência forte de CNPJ sustenta classificação automática,
        # mesmo que haja poucas evidências adicionais.
        doc.sent_to_review = False
        doc.decision_reason = (
            "Classificado automaticamente com base em CNPJ válido da loja."
        )
    elif fragile_store or store_confidence < 0.5:
        doc.sent_to_review = True
        doc.decision_reason = (
            "Loja identificada, mas decisão enviada para revisão manual por baixa confiança."
        )
    else:
        doc.sent_to_review = False
        doc.decision_reason = "Classificado automaticamente com confiança adequada."

    # Explicação textual detalhada
    explanation_lines: List[str] = []
    explanation_lines.append(f"Loja sugerida: {doc.suggested_store or 'nenhuma'}.")
    explanation_lines.append(f"Scores por loja: {doc.store_scores}.")
    explanation_lines.append(
        f"Evidências de loja (aliases e locais): {doc.score_details['matched_store_aliases']}."
    )
    explanation_lines.append(
        f"Fontes de evidência de loja: {doc.score_details['matched_store_sources']}."
    )
    explanation_lines.append(
        f"Tipo de documento sugerido: {doc.suggested_doc_type.value}."
    )
    explanation_lines.append(f"Scores por tipo: { {k.value: v for k, v in doc.doc_type_scores.items()} }.")
    explanation_lines.append(
        f"Evidências de tipo (palavras‑chave): {doc.score_details['matched_type_keywords']}."
    )
    explanation_lines.append(
        f"Fontes de evidência de tipo: {doc.score_details['matched_type_sources']}."
    )
    explanation_lines.append(
        f"Confianças: store={doc.store_confidence}, type={doc.type_confidence}, overall={doc.overall_confidence}."
    )
    if doc.has_strong_store_evidence and doc.strong_evidence_type == "cnpj_match":
        explanation_lines.append(
            "Evidência forte de loja: CNPJ válido correspondente à loja sugerida."
        )
    explanation_lines.append(f"Decisão final: {doc.decision_reason}")

    doc.decision_explanation = "\n".join(explanation_lines)

    return doc

