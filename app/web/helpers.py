"""
Helpers para leitura de dados existentes (reports, pastas).
Não altera o pipeline; apenas consulta.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import load_settings


def get_settings():
    """Carrega configuração atual (para uso nas rotas)."""
    return load_settings()


def _load_report_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def get_latest_report(reports_dir: Path) -> Optional[Dict[str, Any]]:
    """Retorna o conteúdo do relatório JSON mais recente."""
    if not reports_dir.exists():
        return None
    jsons = sorted(reports_dir.glob("report_*.json"), reverse=True)
    if not jsons:
        return None
    return _load_report_json(jsons[0])


def get_reports_from_today(reports_dir: Path) -> List[Dict[str, Any]]:
    """Lista relatórios do dia atual."""
    if not reports_dir.exists():
        return []
    today = datetime.now().strftime("%Y%m%d")
    jsons = [p for p in reports_dir.glob("report_*.json") if today in p.stem]
    out = []
    for p in sorted(jsons, reverse=True):
        data = _load_report_json(p)
        if data:
            out.append(data)
    return out


def dashboard_stats(reports_dir: Path) -> Dict[str, Any]:
    """
    Agrega estatísticas para o dashboard:
    - total_hoje, total_por_loja, revisao_manual_hoje, ocr_hoje
    - ultimos_itens (lista dos últimos processados)
    """
    today_reports = get_reports_from_today(reports_dir)
    latest = get_latest_report(reports_dir)

    total_hoje = 0
    revisao_hoje = 0
    ocr_hoje = 0
    por_loja: Dict[str, int] = {}
    todos_itens: List[Dict[str, Any]] = []

    for data in today_reports:
        resumo = data.get("resumo", {})
        total_hoje += resumo.get("total_arquivos", 0)
        revisao_hoje += resumo.get("total_revisao_manual", 0)
        for item in data.get("itens", []):
            if item.get("ocr_used"):
                ocr_hoje += 1
            loja = item.get("loja_sugerida") or "desconhecido"
            por_loja[loja] = por_loja.get(loja, 0) + 1
            item["_report_timestamp"] = data.get("_timestamp", "")
            todos_itens.append(item)

    # Ordenar por report mais recente (usar nome do arquivo não temos timestamp no JSON)
    # Últimos 50 itens
    ultimos = (latest or {}).get("itens", [])[:50]
    if today_reports and not ultimos:
        for r in today_reports:
            ultimos.extend(r.get("itens", []))
        ultimos = ultimos[:50]

    return {
        "total_hoje": total_hoje,
        "revisao_manual_hoje": revisao_hoje,
        "ocr_hoje": ocr_hoje,
        "por_loja": por_loja,
        "ultimos_itens": ultimos,
        "tem_relatorio_hoje": len(today_reports) > 0,
        "ultimo_relatorio": latest,
    }


def list_review_files(review_dir: Path) -> List[Dict[str, Any]]:
    """
    Lista arquivos em review_manual/ (uma profundidade: store/tipo/nome).
    Retorna lista de dict com: path, name, store, doc_type, mtime.
    """
    if not review_dir.exists():
        return []
    out = []
    for store_path in review_dir.iterdir():
        if not store_path.is_dir():
            continue
        for type_path in store_path.iterdir():
            if not type_path.is_dir():
                continue
            for f in type_path.iterdir():
                if f.is_file():
                    try:
                        mtime = f.stat().st_mtime
                        out.append({
                            "path": f,
                            "name": f.name,
                            "store": store_path.name,
                            "doc_type": type_path.name,
                            "mtime": mtime,
                            "mtime_iso": datetime.fromtimestamp(mtime).isoformat(),
                        })
                    except OSError:
                        pass
    # Também arquivos diretamente em review_manual (sem store/tipo)
    for f in review_dir.iterdir():
        if f.is_file():
            try:
                mtime = f.stat().st_mtime
                out.append({
                    "path": f,
                    "name": f.name,
                    "store": "-",
                    "doc_type": "-",
                    "mtime": mtime,
                    "mtime_iso": datetime.fromtimestamp(mtime).isoformat(),
                })
            except OSError:
                pass
    out.sort(key=lambda x: x["mtime"], reverse=True)
    return out


def list_output_stores(output_dir: Path, aliases: Dict[str, Any]) -> List[Dict[str, str]]:
    """Lista lojas presentes em output/ com nome de exibição."""
    store_names = {
        "ljUbj": "Ubajara",
        "ljIbi": "Ibiapina",
        "ljSb": "São Benedito",
        "ljGba": "Guaraciaba",
        "ljLc": "L&C (Sobral)",
    }
    for code, info in (aliases.get("stores") or {}).items():
        if code not in store_names and isinstance(info, dict):
            store_names[code] = info.get("city", code)
    if not output_dir.exists():
        return []
    out = []
    for p in sorted(output_dir.iterdir()):
        if p.is_dir():
            out.append({"code": p.name, "name": store_names.get(p.name, p.name)})
    return out


def list_store_files(
    output_dir: Path,
    store_code: str,
    doc_type_filter: Optional[str] = None,
    name_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Lista arquivos de uma loja em output/.
    Filtros opcionais: tipo de documento, substring no nome.
    """
    store_path = output_dir / store_code
    if not store_path.exists() or not store_path.is_dir():
        return []
    out = []
    for type_path in store_path.iterdir():
        if not type_path.is_dir():
            continue
        if doc_type_filter and type_path.name != doc_type_filter:
            continue
        for f in type_path.iterdir():
            if not f.is_file():
                continue
            if name_filter and name_filter.lower() not in f.name.lower():
                continue
            try:
                mtime = f.stat().st_mtime
                out.append({
                    "name": f.name,
                    "doc_type": type_path.name,
                    "path": f,
                    "mtime": mtime,
                    "mtime_iso": datetime.fromtimestamp(mtime).isoformat(),
                })
            except OSError:
                pass
    out.sort(key=lambda x: (x["doc_type"], x["mtime"]), reverse=True)
    return out


def system_status(settings) -> Dict[str, Any]:
    """
    Status para exibição (watcher/WhatsApp não são iniciados pelo servidor web).
    Última execução e último erro vêm do último report.
    """
    latest = get_latest_report(settings.paths.reports_dir)
    resumo = (latest or {}).get("resumo", {})
    itens = (latest or {}).get("itens", [])
    ultimo_erro = None
    for i in reversed(itens):
        if i.get("erro"):
            ultimo_erro = i.get("erro")
            break
    # Timestamp do último report: do nome do arquivo
    ultima_exec = None
    if settings.paths.reports_dir.exists():
        jsons = sorted(settings.paths.reports_dir.glob("report_*.json"), reverse=True)
        if jsons:
            stem = jsons[0].stem  # report_20250313-123456
            try:
                part = stem.replace("report_", "")
                ultima_exec = datetime.strptime(part, "%Y%m%d-%H%M%S").isoformat()
            except ValueError:
                ultima_exec = stem
    return {
        "watcher_ativo": False,  # servidor web não inicia watcher
        "whatsapp_ingestion_ativo": False,
        "ocr_habilitado": settings.ocr.enabled,
        "whatsapp_ingestion_habilitado": settings.whatsapp_ingestion.enabled,
        "ultima_execucao": ultima_exec,
        "ultimo_erro": ultimo_erro,
        "total_ultimo_relatorio": resumo.get("total_arquivos"),
        "erros_ultimo_relatorio": resumo.get("total_erros"),
    }
