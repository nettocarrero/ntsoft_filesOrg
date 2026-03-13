from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from app.models import ProcessingResult, ExecutionReport


def _serialize_processing_result(result: ProcessingResult) -> Dict[str, Any]:
    d = result.document
    return {
        "nome_original": d.original_path.name,
        "caminho_original": str(d.original_path),
        # Campos legados (ZIP) para compatibilidade
        "veio_de_zip": d.came_from_zip,
        "zip_root": str(d.zip_root) if d.zip_root else None,
        # Campos genéricos de arquivo compactado
        "veio_de_arquivo_compactado": d.came_from_archive,
        "tipo_arquivo_compactado": d.archive_type,
        "arquivo_compactado_origem": str(d.archive_root) if d.archive_root else None,
        "texto_extraido_status": d.text_status,
        "text_source": d.text_source,
        "ocr_used": d.ocr_used,
        "ocr_success": d.ocr_success,
        "ocr_metadata": d.ocr_metadata,
        "cnpjs_detectados": d.detected_cnpjs,
        "loja_sugerida": d.suggested_store,
        "score_por_loja": d.store_scores,
        "tipo_sugerido": d.suggested_doc_type.value,
        "score_por_tipo": {k.value: v for k, v in d.doc_type_scores.items()},
        "store_confidence": d.store_confidence,
        "type_confidence": d.type_confidence,
        "overall_confidence": d.overall_confidence,
        "has_strong_store_evidence": d.has_strong_store_evidence,
        "strong_evidence_type": d.strong_evidence_type,
        "score_details": d.score_details,
        "destino_final": str(d.destination_path) if d.destination_path else None,
        "motivo_decisao": d.decision_reason,
        "explicacao_decisao": d.decision_explanation,
        "ignorado_por_regra": d.ignored,
        "enviado_para_revisao": d.sent_to_review,
        "status_processamento": result.status.value,
        "erro": result.error_message,
    }


def generate_reports(
    report_dir: Path, results: List[ProcessingResult]
) -> ExecutionReport:
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    exec_report = ExecutionReport(results=results)

    data = {
        "resumo": {
            "total_arquivos": exec_report.total_files,
            "total_arquivos_compactados": exec_report.total_from_archives,
            "total_vindos_de_zip": exec_report.total_from_zip,
            "total_vindos_de_rar": exec_report.total_from_rar,
            "total_classificados_automaticamente": exec_report.total_classified_automatic,
            "total_revisao_manual": exec_report.total_review,
            "total_erros": exec_report.total_errors,
            "total_com_cnpj": exec_report.total_with_cnpj,
        },
        "itens": [_serialize_processing_result(r) for r in results],
    }

    json_path = report_dir / f"report_{timestamp}.json"
    txt_path = report_dir / f"report_{timestamp}.txt"

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    with txt_path.open("w", encoding="utf-8") as f:
        resumo = data["resumo"]
        f.write("Resumo da execução\n")
        for k, v in resumo.items():
            f.write(f"- {k}: {v}\n")
        f.write("\nDetalhes por arquivo:\n\n")
        for item in data["itens"]:
            f.write(f"Arquivo: {item['nome_original']}\n")
            f.write(f"  Caminho original: {item['caminho_original']}\n")
            f.write(f"  Veio de ZIP (legado): {item['veio_de_zip']}\n")
            f.write(f"  Veio de arquivo compactado: {item['veio_de_arquivo_compactado']}\n")
            f.write(f"  Tipo arquivo compactado: {item['tipo_arquivo_compactado']}\n")
            f.write(f"  Arquivo compactado origem: {item['arquivo_compactado_origem']}\n")
            f.write(f"  Texto extraído status: {item['texto_extraido_status']}\n")
            f.write(f"  Fonte do texto: {item['text_source']}\n")
            f.write(f"  OCR usado: {item['ocr_used']}, sucesso: {item['ocr_success']}\n")
            f.write(f"  OCR metadata: {item['ocr_metadata']}\n")
            f.write(f"  Ignorado por regra: {item['ignorado_por_regra']}\n")
            f.write(f"  CNPJs detectados: {', '.join(item['cnpjs_detectados']) if item['cnpjs_detectados'] else 'nenhum'}\n")
            f.write(f"  Loja sugerida: {item['loja_sugerida']}\n")
            f.write(f"  Tipo sugerido: {item['tipo_sugerido']}\n")
            f.write(
                "  Confiança: "
                f"store={item['store_confidence']}, "
                f"type={item['type_confidence']}, "
                f"overall={item['overall_confidence']}\n"
            )
            f.write(f"  Enviado para revisão: {item['enviado_para_revisao']}\n")
            f.write(f"  Destino final: {item['destino_final']}\n")
            f.write(f"  Motivo decisão: {item['motivo_decisao']}\n")
            f.write(f"  Evidência forte de loja: {item.get('has_strong_store_evidence', False)} ({item.get('strong_evidence_type', 'nenhuma')})\n")
            f.write("  Evidências:\n")
            f.write(f"    matched_store_aliases: {item['score_details'].get('matched_store_aliases', [])}\n")
            f.write(f"    matched_store_sources: {item['score_details'].get('matched_store_sources', [])}\n")
            f.write(f"    matched_type_keywords: {item['score_details'].get('matched_type_keywords', [])}\n")
            f.write(f"    matched_type_sources: {item['score_details'].get('matched_type_sources', [])}\n")
            f.write("  Explicação detalhada da decisão:\n")
            f.write(f"{item['explicacao_decisao']}\n")
            f.write(f"  Status processamento: {item['status_processamento']}\n")
            if item["erro"]:
                f.write(f"  Erro: {item['erro']}\n")
            f.write("\n")

    return exec_report

