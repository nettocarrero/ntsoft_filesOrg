"""
Helpers para leitura de dados existentes (reports, pastas).
Não altera o pipeline; apenas consulta.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from app.config import load_settings
from app.services.document_finance_parser import read_payment_meta_file
from app.services.organizer_service import OUTPUT_FOLDERS


def get_settings():
    """Carrega configuração atual (para uso nas rotas)."""
    return load_settings()


def is_local_client(client_host: str | None) -> bool:
    """
    True se a requisição veio do localhost (PC onde o servidor roda).
    Usado para permitir edição de configurações e botões de manutenção apenas no PC principal.
    """
    return client_host in ("127.0.0.1", "::1")


def load_ip_users() -> Dict[str, str]:
    """Carrega mapeamento IP -> nome de usuário (app/data/ip_users.json)."""
    settings = get_settings()
    path = settings.paths.data_dir / "ip_users.json"
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_ip_users(mapping: Dict[str, str]) -> None:
    """Salva mapeamento IP -> nome em app/data/ip_users.json."""
    settings = get_settings()
    path = settings.paths.data_dir / "ip_users.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)


def load_file_sender_registry() -> Dict[str, str]:
    """Carrega registro path_resolvido -> nome de quem enviou (app/data/file_sender_registry.json)."""
    settings = get_settings()
    path = settings.paths.data_dir / "file_sender_registry.json"
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def update_file_sender_registry(entries: Dict[str, str]) -> None:
    """Atualiza o registro de quem enviou (merge com o existente)."""
    settings = get_settings()
    reg_path = settings.paths.data_dir / "file_sender_registry.json"
    current = load_file_sender_registry()
    current.update(entries)
    reg_path.parent.mkdir(parents=True, exist_ok=True)
    with reg_path.open("w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)


def load_whatsapp_input_paths() -> set:
    """Carrega conjunto de paths (str) em input que vieram do WhatsApp (app/data/whatsapp_input_paths.json)."""
    settings = get_settings()
    path = settings.paths.data_dir / "whatsapp_input_paths.json"
    if not path.exists():
        return set()
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return set(data) if isinstance(data, list) else set()
    except Exception:
        return set()


def add_path_to_whatsapp_origins(input_path: Path) -> None:
    """Registra que este path em input/ veio do WhatsApp (para marcar destino como 'classificado de forma automatica')."""
    settings = get_settings()
    reg_path = settings.paths.data_dir / "whatsapp_input_paths.json"
    current = list(load_whatsapp_input_paths())
    key = str(input_path.resolve())
    if key not in current:
        current.append(key)
    reg_path.parent.mkdir(parents=True, exist_ok=True)
    with reg_path.open("w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)


def remove_whatsapp_input_paths(paths_to_remove: List[str]) -> None:
    """Remove paths do registro de origens WhatsApp (após processamento)."""
    current = load_whatsapp_input_paths()
    for p in paths_to_remove:
        current.discard(p)
    settings = get_settings()
    reg_path = settings.paths.data_dir / "whatsapp_input_paths.json"
    reg_path.parent.mkdir(parents=True, exist_ok=True)
    with reg_path.open("w", encoding="utf-8") as f:
        json.dump(list(current), f, ensure_ascii=False, indent=2)


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


def archive_reports(reports_dir: Path) -> tuple[int, Path | None]:
    """
    Move todos os report_*.json e report_*.txt para uma subpasta archive_<timestamp>.
    Não remove nada; apenas arquiva. Assim os contadores do dashboard zeram.
    Retorna (quantidade de arquivos movidos, caminho da pasta de arquivo ou None).
    Não mexe em app.log nem em outros arquivos.
    """
    if not reports_dir.exists():
        return 0, None
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_dir = reports_dir / f"archive_{stamp}"
    count = 0
    for pattern in ("report_*.json", "report_*.txt"):
        for p in reports_dir.glob(pattern):
            if p.is_file():
                try:
                    archive_dir.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(p), str(archive_dir / p.name))
                    count += 1
                except (OSError, shutil.Error):
                    pass
    return count, archive_dir if archive_dir.exists() else None


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
        "ljKlc": "KLC (Sobral)",
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

    # Reordena lojas na ordem desejada no explorador:
    # UBAJARA, IBIAPINA, SÃO BENEDITO, GUARACIABA, e por último L&C / KLC.
    def _store_sort_key(item: Dict[str, str]) -> tuple[int, str]:
        code = item.get("code", "")
        order_map = {
            "ljUbj": 1,  # Ubajara
            "ljIbi": 2,  # Ibiapina
            "ljSb": 3,   # São Benedito
            "ljGba": 4,  # Guaraciaba
            "ljLc": 5,   # L&C (Sobral)
            "ljKlc": 6,  # KLC (Sobral)
        }
        base = order_map.get(code, 100)
        return (base, item.get("name", "").lower())

    out.sort(key=_store_sort_key)
    return out


def list_store_years(output_dir: Path, store_code: str) -> List[str]:
    """Lista anos presentes na loja (subdirs 4 dígitos). Estrutura nova."""
    store_path = output_dir / store_code
    if not store_path.exists() or not store_path.is_dir():
        return []
    years = []
    for p in store_path.iterdir():
        if p.is_dir() and len(p.name) == 4 and p.name.isdigit():
            years.append(p.name)
    return sorted(years, reverse=True)


def list_store_months(output_dir: Path, store_code: str, year: str) -> List[str]:
    """Lista meses presentes em output/loja/ano/ (subdirs 01-12)."""
    period_path = output_dir / store_code / year
    if not period_path.exists() or not period_path.is_dir():
        return []
    months = []
    for p in period_path.iterdir():
        if (
            p.is_dir()
            and len(p.name) == 2
            and p.name.isdigit()
            and 1 <= int(p.name) <= 12
        ):
            months.append(p.name)
    # Ordena meses do mais antigo para o mais recente: 01, 02, 03, ...
    return sorted(months)


def list_store_types_in_period(
    output_dir: Path, store_code: str, year: str, month: str
) -> List[str]:
    """Lista pastas de tipo em output/loja/ano/mes/ (pagamentos, notas_fiscais, etc.)."""
    type_path = output_dir / store_code / year / month
    if not type_path.exists() or not type_path.is_dir():
        return []
    return [p.name for p in type_path.iterdir() if p.is_dir()]


def list_store_legacy_types(output_dir: Path, store_code: str) -> List[str]:
    """Lista pastas de tipo na estrutura antiga (loja/tipo). Subdirs que não são 4 dígitos."""
    store_path = output_dir / store_code
    if not store_path.exists() or not store_path.is_dir():
        return []
    return [
        p.name
        for p in store_path.iterdir()
        if p.is_dir() and not (len(p.name) == 4 and p.name.isdigit())
    ]


def _collect_files_from_dir(
    type_path: Path,
    type_name: str,
    name_filter: Optional[str],
    date_from: Optional[date],
    date_to: Optional[date],
) -> List[Dict[str, Any]]:
    out = []
    for f in type_path.iterdir():
        if not f.is_file():
            continue
        # Não exibir arquivos de metadados (.meta.json) no explorador
        if f.name.endswith(".meta.json"):
            continue
        if name_filter and name_filter.lower() not in f.name.lower():
            continue
        try:
            mtime = f.stat().st_mtime
            dt = datetime.fromtimestamp(mtime)
            file_date = dt.date()
            if date_from is not None and file_date < date_from:
                continue
            if date_to is not None and file_date > date_to:
                continue
            out.append({
                "name": f.name,
                "stem": Path(f.name).stem,
                "extension": Path(f.name).suffix,
                "doc_type": type_name,
                "path": f,
                "mtime": mtime,
                "mtime_iso": dt.isoformat(),
                "mtime_br": dt.strftime("%d/%m/%Y %H:%M:%S"),
                "hint": str(f),
            })
        except OSError:
            pass
    return out


def list_store_files(
    output_dir: Path,
    store_code: str,
    year: Optional[str] = None,
    month: Optional[str] = None,
    doc_type_filter: Optional[str] = None,
    name_filter: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> List[Dict[str, Any]]:
    """
    Lista arquivos de uma loja em output/.
    Nova estrutura: se year e month informados, usa output/loja/ano/mes/tipo/.
    Estrutura legada: se year/month não informados, usa output/loja/tipo/ (subdirs que não são ano).
    """
    store_path = output_dir / store_code
    if not store_path.exists() or not store_path.is_dir():
        return []
    out = []
    if year and month:
        period_path = store_path / year / month
        if not period_path.exists() or not period_path.is_dir():
            return []
        for type_path in period_path.iterdir():
            if not type_path.is_dir():
                continue
            if doc_type_filter and type_path.name != doc_type_filter:
                continue
            out.extend(
                _collect_files_from_dir(
                    type_path, type_path.name, name_filter, date_from, date_to
                )
            )
    else:
        for type_path in store_path.iterdir():
            if not type_path.is_dir():
                continue
            if len(type_path.name) == 4 and type_path.name.isdigit():
                continue
            if doc_type_filter and type_path.name != doc_type_filter:
                continue
            out.extend(
                _collect_files_from_dir(
                    type_path, type_path.name, name_filter, date_from, date_to
                )
            )
    out.sort(key=lambda x: x["mtime"], reverse=True)
    registry = load_file_sender_registry()
    for item in out:
        item["sent_by"] = registry.get(str(item["path"].resolve()), "-")
        _enrich_file_with_payment_meta(item)
    return out


def _enrich_file_with_payment_meta(item: Dict[str, Any]) -> None:
    """Preenche due_date e amount a partir de arquivo .meta.json, se existir."""
    meta = read_payment_meta_file(item["path"])
    if not meta:
        item["payment_due_date"] = None
        item["payment_due_date_br"] = None
        item["payment_amount"] = None
        item["payment_amount_br"] = None
        return
    due = meta.get("due_date")
    amount = meta.get("amount")
    item["payment_due_date"] = due
    item["payment_due_date_br"] = _format_date_br(due) if due else None
    item["payment_amount"] = amount
    item["payment_amount_br"] = _format_amount_br(amount) if amount is not None else None


def _format_date_br(iso_date: str) -> str:
    """Converte YYYY-MM-DD em dd/mm/yyyy."""
    if not iso_date or len(iso_date) < 10:
        return "-"
    try:
        y, m, d = iso_date[:10].split("-")
        return f"{d}/{m}/{y}"
    except ValueError:
        return "-"


def _format_amount_br(value: float) -> str:
    """Formata valor como R$ 1.234,56."""
    try:
        return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "-"


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
