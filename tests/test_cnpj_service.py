from app.services.cnpj_service import (
    extract_cnpjs_from_text,
    extract_cnpjs_with_ocr_robust,
    match_cnpj_to_store,
    build_cnpj_index,
)
from app.config import load_settings


def test_extract_cnpj_with_punctuation():
    text = "CNPJ: 12.345.678/0001-90"
    cnpjs = extract_cnpjs_from_text(text)
    assert cnpjs == ["12345678000190"]


def test_extract_cnpj_without_punctuation():
    text = "O CNPJ da empresa é 12345678000190."
    cnpjs = extract_cnpjs_from_text(text)
    assert "12345678000190" in cnpjs


def test_multiple_cnpjs_in_text():
    text = "Primeiro: 12.345.678/0001-90 e depois 11.222.333/0001-44."
    cnpjs = extract_cnpjs_from_text(text)
    assert "12345678000190" in cnpjs
    assert "11222333000144" in cnpjs


def test_match_cnpj_to_store():
    settings = load_settings()
    aliases = settings.aliases
    index = build_cnpj_index(aliases)

    # usar um dos CNPJs cadastrados em aliases.json
    some_cnpj = next(iter(index.keys()))
    store = match_cnpj_to_store(some_cnpj, aliases)

    assert store == index[some_cnpj]


def test_ocr_robust_normalization_simple():
    text = "CNPJ: O7.439.697/OOO1-4O"
    cnpjs, meta = extract_cnpjs_with_ocr_robust(text, is_ocr=True)
    assert "07439697000140" in cnpjs
    assert meta["detection_mode"] in {"ocr_robust", "mixed"}


def test_ocr_robust_compact_digits_with_letters():
    text = "CNPJ 07439697OOO14O"
    cnpjs, meta = extract_cnpjs_with_ocr_robust(text, is_ocr=True)
    assert "07439697000140" in cnpjs


def test_no_false_positive_on_random_text():
    text = "Este texto não contém nenhum número parecido com CNPJ."
    cnpjs, meta = extract_cnpjs_with_ocr_robust(text, is_ocr=True)
    assert cnpjs == []

