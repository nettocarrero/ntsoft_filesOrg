from app.utils.path_utils import (
    sanitize_windows_path_part,
    sanitize_archive_member_path,
)


def test_sanitize_windows_path_part_trailing_space():
    assert sanitize_windows_path_part("BOLETOS LINEU PINZON ") == "BOLETOS LINEU PINZON"


def test_sanitize_windows_path_part_trailing_dot():
    assert sanitize_windows_path_part("arquivo.") == "arquivo"


def test_sanitize_windows_path_part_invalid_chars():
    assert (
        sanitize_windows_path_part('relatorio:marco?.pdf')
        == "relatoriomarco.pdf"
    )


def test_sanitize_windows_path_part_space_before_extension():
    assert sanitize_windows_path_part("arquivo .pdf") == "arquivo.pdf"
    assert (
        sanitize_windows_path_part("CHOCOBALAS GUARACIABA VAREJÃO .pdf")
        == "CHOCOBALAS GUARACIABA VAREJÃO.pdf"
    )


def test_sanitize_archive_member_path_complex():
    # múltiplas partes problemáticas
    path = "pasta ruim ./subpasta /arquivo .pdf"
    sanitized = sanitize_archive_member_path(path)
    # Apenas valida que não há '..' e que partes não estão vazias
    parts = list(sanitized.parts)
    assert all(part and part != ".." for part in parts)


def test_sanitize_archive_member_path_prevents_traversal():
    path = "../fora.pdf"
    sanitized = sanitize_archive_member_path(path)
    # não deve conter '..' e deve gerar um nome seguro
    assert ".." not in sanitized.parts
    assert sanitized.name != ""

