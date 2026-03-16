from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

from app.config import PathsConfig
from app.models import DocumentInfo
from app.models.enums import DocumentType


# Mapeamento tipo de documento -> pasta na estrutura output/loja/ano/mes/
# Boletos e guias (taxa) vão para "pagamentos"
DOC_TYPE_TO_OUTPUT_FOLDER = {
    DocumentType.BOLETO: "pagamentos",
    DocumentType.TAXA: "pagamentos",
    DocumentType.NOTA_FISCAL: "notas_fiscais",
    DocumentType.NOTA_SERVICO: "notas_servico",
    DocumentType.COMPROVANTE: "comprovantes",
    DocumentType.DESCONHECIDO: "outros",
}

OUTPUT_FOLDERS = ("pagamentos", "notas_fiscais", "notas_servico", "comprovantes", "outros")


def doc_type_value_to_output_folder(doc_type_value: str) -> str:
    """Converte valor do enum (ex: 'boleto') para nome da pasta (ex: 'pagamentos')."""
    try:
        dt = DocumentType(doc_type_value)
        return DOC_TYPE_TO_OUTPUT_FOLDER.get(dt, "outros")
    except ValueError:
        return "outros"


def _output_folder_for_type(doc_type: DocumentType) -> str:
    """Retorna o nome da pasta para o tipo de documento na estrutura nova."""
    return DOC_TYPE_TO_OUTPUT_FOLDER.get(doc_type, "outros")


def _build_output_path(doc: DocumentInfo, paths: PathsConfig) -> Path:
    """
    Monta o caminho de destino: output/{loja}/{ano}/{mes}/{tipo}/arquivo.ext
    Para revisão manual: review_manual/{loja}/{tipo}/arquivo.ext (estrutura antiga).
    """
    if doc.sent_to_review or not doc.suggested_store:
        base = paths.review_manual_dir
        store_folder = doc.suggested_store or "desconhecido"
        type_folder = doc.suggested_doc_type.value
        return base / store_folder / type_folder / (doc.extracted_path or doc.original_path).name
    # Nova estrutura: output/loja/ano/mes/tipo/arquivo
    base = paths.output_dir
    store_folder = doc.suggested_store
    doc_date = doc.document_date or date.today()
    year_folder = doc_date.strftime("%Y")
    month_folder = doc_date.strftime("%m")
    type_folder = _output_folder_for_type(doc.suggested_doc_type)
    filename = (doc.extracted_path or doc.original_path).name
    return base / store_folder / year_folder / month_folder / type_folder / filename


def organize_document(doc: DocumentInfo, paths: PathsConfig) -> DocumentInfo:
    src = doc.extracted_path or doc.original_path
    destination = _build_output_path(doc, paths)
    destination.parent.mkdir(parents=True, exist_ok=True)

    shutil.copy2(src, destination)
    doc.destination_path = destination
    return doc
