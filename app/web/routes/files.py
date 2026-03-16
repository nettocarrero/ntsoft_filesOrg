from __future__ import annotations

from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Request, Query, Form
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse

from app.web.helpers import (
    get_settings,
    list_output_stores,
    list_store_files,
    list_store_years,
    list_store_months,
    list_store_types_in_period,
    list_store_legacy_types,
)

router = APIRouter()


def _parse_date(value: str | None):
    """Converte YYYY-MM-DD em date ou None."""
    if not value or not value.strip():
        return None
    try:
        return datetime.strptime(value.strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


# Nomes dos meses para exibição no explorador
MONTH_NAMES = {
    "01": "Janeiro", "02": "Fevereiro", "03": "Março", "04": "Abril",
    "05": "Maio", "06": "Junho", "07": "Julho", "08": "Agosto",
    "09": "Setembro", "10": "Outubro", "11": "Novembro", "12": "Dezembro",
}


def _build_files_context(
    settings,
    store: str | None,
    ano: str | None,
    mes: str | None,
    tipo: str | None,
    legacy: bool,
    store_name: str,
    stores: list,
):
    """Decide nível de navegação e monta breadcrumb, folders e files."""
    output_dir = settings.paths.output_dir
    years = list_store_years(output_dir, store) if store else []
    legacy_types = list_store_legacy_types(output_dir, store) if store else []
    months: list = []
    types_in_period: list = []
    level = "none"
    breadcrumb = []
    folders = []
    files_list: list = []

    if not store:
        return {
            "level": "none",
            "breadcrumb": [{"label": "Explorador", "url": "/files"}],
            "folders": [],
            "files": [],
            "years": [],
            "months": [],
            "types_in_period": [],
            "legacy_types": [],
            "store_name": "",
            "filter_ano": "",
            "filter_mes": "",
            "filter_tipo": "",
        }

    base = [{"label": "Explorador", "url": "/files"}, {"label": store_name, "url": f"/files?store={quote(store, safe='')}"}]

        if legacy:
        # Navegação legada: store → Arquivos legados → tipo → arquivos
        breadcrumb = base + [{"label": "Arquivos legados", "url": f"/files?store={quote(store, safe='')}&legacy=1"}]
        if not tipo:
            level = "legacy"
            folders = [
                {
                    "name": t.upper(),
                    "url": f"/files?store={quote(store, safe='')}&legacy=1&tipo={quote(t, safe='')}",
                }
                for t in sorted(legacy_types)
            ]
        else:
            level = "legacy_files"
            breadcrumb = breadcrumb + [{"label": tipo, "url": f"/files?store={quote(store, safe='')}&legacy=1&tipo={quote(tipo, safe='')}"}]
            files_list = list_store_files(
                output_dir, store, year=None, month=None,
                doc_type_filter=tipo, name_filter=None, date_from=None, date_to=None,
            )
            for f in files_list:
                f["path_url"] = quote(str(f["path"]), safe="")
        return {
            "level": level,
            "breadcrumb": breadcrumb,
            "folders": folders,
            "files": files_list,
            "years": years,
            "months": [],
            "types_in_period": [],
            "legacy_types": legacy_types,
            "store_name": store_name,
            "filter_ano": ano or "",
            "filter_mes": mes or "",
            "filter_tipo": tipo or "",
        }

    # Estrutura nova: store → ano → mês → tipo → arquivos
    if not ano:
        level = "store_root"
        breadcrumb = base
        folders = [
            {
                "name": str(y).upper(),
                "url": f"/files?store={quote(store, safe='')}&ano={quote(y, safe='')}",
            }
            for y in years
        ]
        if legacy_types:
            folders.append(
                {
                    "name": "ARQUIVOS LEGADOS",
                    "url": f"/files?store={quote(store, safe='')}&legacy=1",
                }
            )
        return {
            "level": level,
            "breadcrumb": breadcrumb,
            "folders": folders,
            "files": [],
            "years": years,
            "months": [],
            "types_in_period": [],
            "legacy_types": legacy_types,
            "store_name": store_name,
            "filter_ano": "",
            "filter_mes": "",
            "filter_tipo": "",
        }

    months = list_store_months(output_dir, store, ano)
    if not mes:
        level = "year"
        breadcrumb = base + [{"label": ano, "url": f"/files?store={quote(store, safe='')}&ano={quote(ano, safe='')}"}]
        folders = [
            {
                "name": f"{m} - {MONTH_NAMES.get(m, m)}".upper(),
                "url": f"/files?store={quote(store, safe='')}&ano={quote(ano, safe='')}&mes={quote(m, safe='')}",
            }
            for m in months
        ]
        return {
            "level": level,
            "breadcrumb": breadcrumb,
            "folders": folders,
            "files": [],
            "years": years,
            "months": months,
            "types_in_period": [],
            "legacy_types": legacy_types,
            "store_name": store_name,
            "filter_ano": ano,
            "filter_mes": "",
            "filter_tipo": "",
        }

    types_in_period = list_store_types_in_period(output_dir, store, ano, mes)
    if not tipo:
        level = "month"
        mes_label = f"{mes} - {MONTH_NAMES.get(mes, mes)}".upper()
        breadcrumb = base + [
            {"label": ano, "url": f"/files?store={quote(store, safe='')}&ano={quote(ano, safe='')}"},
            {"label": mes_label, "url": f"/files?store={quote(store, safe='')}&ano={quote(ano, safe='')}&mes={quote(mes, safe='')}"},
        ]
        folders = [
            {
                "name": t.upper(),
                "url": f"/files?store={quote(store, safe='')}&ano={quote(ano, safe='')}&mes={quote(mes, safe='')}&tipo={quote(t, safe='')}",
            }
            for t in sorted(types_in_period)
        ]
        return {
            "level": level,
            "breadcrumb": breadcrumb,
            "folders": folders,
            "files": [],
            "years": years,
            "months": months,
            "types_in_period": types_in_period,
            "legacy_types": legacy_types,
            "store_name": store_name,
            "filter_ano": ano,
            "filter_mes": mes,
            "filter_tipo": "",
        }

    level = "files"
    tipo_label = tipo
    breadcrumb = base + [
        {"label": ano, "url": f"/files?store={quote(store, safe='')}&ano={quote(ano, safe='')}"},
        {"label": f"{mes} - {MONTH_NAMES.get(mes, mes)}", "url": f"/files?store={quote(store, safe='')}&ano={quote(ano, safe='')}&mes={quote(mes, safe='')}"},
        {"label": tipo_label, "url": f"/files?store={quote(store, safe='')}&ano={quote(ano, safe='')}&mes={quote(mes, safe='')}&tipo={quote(tipo, safe='')}"},
    ]
    date_from = _parse_date(None)  # will pass from request
    date_to = _parse_date(None)
    files_list = list_store_files(
        output_dir, store, year=ano, month=mes, doc_type_filter=tipo,
        name_filter=None, date_from=date_from, date_to=date_to,
    )
    for f in files_list:
        f["path_url"] = quote(str(f["path"]), safe="")
    return {
        "level": level,
        "breadcrumb": breadcrumb,
        "folders": [],
        "files": files_list,
        "years": years,
        "months": months,
        "types_in_period": types_in_period,
        "legacy_types": legacy_types,
        "store_name": store_name,
        "filter_ano": ano,
        "filter_mes": mes,
        "filter_tipo": tipo,
    }


@router.get("/files", response_class=HTMLResponse)
async def files_page(
    request: Request,
    store: str | None = Query(None),
    ano: str | None = Query(None),
    mes: str | None = Query(None),
    tipo: str | None = Query(None),
    legacy: str | None = Query(None, description="1 = ver estrutura legada"),
    nome: str | None = Query(None),
    data_de: str | None = Query(None),
    data_ate: str | None = Query(None),
    renamed: str | None = Query(None),
    deleted: str | None = Query(None),
):
    settings = get_settings()
    stores = list_output_stores(settings.paths.output_dir, settings.aliases)
    store_name = next((s["name"] for s in stores if s["code"] == store), store) if store else ""
    use_legacy = legacy == "1"

    ctx = _build_files_context(
        settings, store, ano, mes, tipo, use_legacy, store_name, stores
    )
    # Aplicar filtro por nome e data quando estamos em nível de arquivos
    if ctx["files"] and (nome or data_de or data_ate):
        date_from = _parse_date(data_de)
        date_to = _parse_date(data_ate)
        output_dir = settings.paths.output_dir
        ctx["files"] = list_store_files(
            output_dir, store,
            year=None if use_legacy else (ctx.get("filter_ano") or None),
            month=None if use_legacy else (ctx.get("filter_mes") or None),
            doc_type_filter=ctx.get("filter_tipo") or None,
            name_filter=nome, date_from=date_from, date_to=date_to,
        )
        for f in ctx["files"]:
            f["path_url"] = quote(str(f["path"]), safe="")

    return request.app.state.templates.TemplateResponse(
        "files.html",
        {
            "request": request,
            "stores": stores,
            "selected_store": store,
            "store_name": store_name,
            "breadcrumb": ctx["breadcrumb"],
            "level": ctx["level"],
            "folders": ctx["folders"],
            "files": ctx["files"],
            "years": ctx["years"],
            "months": ctx["months"],
            "types_in_period": ctx["types_in_period"],
            "legacy_types": ctx["legacy_types"],
            "filter_ano": ctx["filter_ano"],
            "filter_mes": ctx["filter_mes"],
            "filter_tipo": ctx["filter_tipo"],
            "filter_nome": nome or "",
            "filter_data_de": data_de or "",
            "filter_data_ate": data_ate or "",
            "renamed": renamed == "1",
            "deleted": deleted == "1",
        },
    )


def _resolve_output_path(path_str: str, output_dir: Path) -> Path | None:
    """Resolve path garantindo que está dentro de output_dir."""
    p = Path(path_str)
    if not p.is_absolute():
        p = output_dir / path_str
    try:
        resolved = p.resolve()
        output_resolved = output_dir.resolve()
        resolved.relative_to(output_resolved)
        return resolved if resolved.exists() and resolved.is_file() else None
    except (OSError, RuntimeError, ValueError):
        return None


@router.get("/files/download")
async def files_download(
    path: str = Query(..., description="Caminho do arquivo"),
):
    """Download do arquivo organizado."""
    settings = get_settings()
    resolved = _resolve_output_path(path, settings.paths.output_dir)
    if not resolved:
        return {"error": "Arquivo não encontrado"}
    return FileResponse(resolved, filename=resolved.name)


@router.get("/files/view")
async def files_view(
    path: str = Query(..., description="Caminho do arquivo"),
):
    """Abre o arquivo em nova aba (visualização inline, ex.: PDF)."""
    settings = get_settings()
    resolved = _resolve_output_path(path, settings.paths.output_dir)
    if not resolved:
        return {"error": "Arquivo não encontrado"}
    media_type = "application/pdf" if resolved.suffix.lower() == ".pdf" else None
    return FileResponse(
        resolved,
        filename=resolved.name,
        media_type=media_type,
        headers={"Content-Disposition": "inline"},
    )


@router.get("/files/rename", response_class=HTMLResponse)
async def files_rename_page(
    request: Request,
    path: str = Query(..., description="Caminho do arquivo"),
    store: str | None = Query(None),
):
    """Página com formulário para renomear o arquivo."""
    settings = get_settings()
    resolved = _resolve_output_path(path, settings.paths.output_dir)
    if not resolved:
        return HTMLResponse(content="<h1>Arquivo não encontrado</h1>", status_code=404)
    return request.app.state.templates.TemplateResponse(
        "files_rename.html",
        {
            "request": request,
            "path_value": str(resolved),
            "current_name": resolved.name,
            "store": store or "",
        },
    )


def _safe_basename(name: str) -> str:
    """Retorna apenas o nome do arquivo, sem path (segurança)."""
    return Path(name).name.strip() if name else ""


def _files_back_url(
    store: str,
    ano: str | None = None,
    mes: str | None = None,
    tipo: str | None = None,
    legacy: bool = False,
    extra: str = "",
) -> str:
    """Monta URL de retorno do explorador preservando nível de navegação."""
    if not store:
        return f"/files{extra}"
    params = ["store=" + quote(store, safe="")]
    if legacy:
        params.append("legacy=1")
        if tipo:
            params.append("tipo=" + quote(tipo, safe=""))
    else:
        if ano:
            params.append("ano=" + quote(ano, safe=""))
        if mes:
            params.append("mes=" + quote(mes, safe=""))
        if tipo:
            params.append("tipo=" + quote(tipo, safe=""))
    return "/files?" + "&".join(params) + extra


@router.post("/files/rename", response_class=RedirectResponse)
async def files_rename_do(
    path: str = Form(...),
    new_name: str = Form(...),
    store: str = Form(""),
    ano: str = Form(""),
    mes: str = Form(""),
    tipo: str = Form(""),
    legacy: str = Form(""),
):
    """Renomeia o arquivo (mesmo diretório). Redireciona de volta ao explorador."""
    settings = get_settings()
    resolved = _resolve_output_path(path, settings.paths.output_dir)
    if not resolved:
        return RedirectResponse(url="/files?error=arquivo_nao_encontrado", status_code=303)
    safe_name = _safe_basename(new_name)
    if not safe_name:
        return RedirectResponse(
            url=f"/files/rename?path={quote(path, safe='')}&store={quote(store, safe='')}&error=nome_vazio",
            status_code=303,
        )
    new_path = resolved.parent / safe_name
    if new_path.exists() and new_path != resolved:
        return RedirectResponse(
            url=f"/files/rename?path={quote(path, safe='')}&store={quote(store, safe='')}&error=ja_existe",
            status_code=303,
        )
    try:
        resolved.rename(new_path)
    except OSError:
        return RedirectResponse(
            url=f"/files/rename?path={quote(path, safe='')}&store={quote(store, safe='')}&error=erro",
            status_code=303,
        )
    back = _files_back_url(store, ano or None, mes or None, tipo or None, legacy == "1", "&renamed=1")
    return RedirectResponse(url=back, status_code=303)


@router.post("/files/delete", response_class=RedirectResponse)
async def files_delete(
    path: str = Form(...),
    store: str = Form(""),
    ano: str = Form(""),
    mes: str = Form(""),
    tipo: str = Form(""),
    legacy: str = Form(""),
):
    """Exclui o arquivo. Redireciona de volta ao explorador."""
    settings = get_settings()
    resolved = _resolve_output_path(path, settings.paths.output_dir)
    if not resolved:
        return RedirectResponse(url="/files?error=arquivo_nao_encontrado", status_code=303)
    try:
        resolved.unlink()
    except OSError:
        return RedirectResponse(url="/files?error=erro_excluir", status_code=303)
    back = _files_back_url(store, ano or None, mes or None, tipo or None, legacy == "1", "&deleted=1")
    return RedirectResponse(url=back, status_code=303)
