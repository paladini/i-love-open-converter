from __future__ import annotations

import re
from pathlib import Path

import pytest

from i_love_open_converter.raw_ops import RAW_EXTENSIONS

ROOT = Path(__file__).resolve().parents[1]
READMES = ("README.md", "README.pt-BR.md")


def _matrix_rows(filename: str) -> tuple[str, list[list[str]]]:
    content = (ROOT / filename).read_text(encoding="utf-8")
    heading = (
        "### Formats and limits" if filename == "README.md" else "### Formatos e limites"
    )
    next_heading = (
        "## Quick start with Docker"
        if filename == "README.md"
        else "## Início rápido com Docker"
    )
    section = content[content.index(heading) : content.index(next_heading)]
    table = [line for line in section.splitlines() if line.startswith("|")]
    rows = [[cell.strip() for cell in line.strip("|").split("|")] for line in table[2:]]
    return content, rows


@pytest.mark.parametrize("filename", READMES)
def test_format_matrix_lists_only_shipped_conversion_paths(filename):
    content, rows = _matrix_rows(filename)
    generic = next(
        row
        for row in rows
        if "generic image conversion" in row[1].lower()
        or "conversão genérica" in row[1].lower()
    )
    output = generic[2].lower()
    assert all(token in output for token in ("jpeg", "png", "gif", "webp"))
    assert "one-frame" in output or "um quadro" in output

    animated = next(
        row
        for row in rows
        if "animated gif" in row[1].lower() or "gif animado" in row[1].lower()
    )
    assert "png" in animated[2].lower() and "gif" in animated[2].lower()
    assert any("svg" in row[0].lower() for row in rows)
    assert any("psd" in row[0].lower() for row in rows)
    assert any("heic" in row[0].lower() and "heif" in row[0].lower() for row in rows)

    raw_row = next(
        row
        for row in rows
        if "camera raw" in row[0].lower() or "raw de câmera" in row[0].lower()
    )
    assert set(re.findall(r"\.[a-z0-9]+", raw_row[0].lower())) == RAW_EXTENSIONS
    assert "100 m" in raw_row[2].lower()

    pdf_row = next(
        row
        for row in rows
        if "unencrypted pdf" in row[0].lower() or "pdf sem criptografia" in row[0].lower()
    )
    assert pdf_row[2].strip().lower() == "pdf"
    assert "html" not in pdf_row[2].lower()
    assert "translate" in pdf_row[1].lower() or "traduzir" in pdf_row[1].lower()
    assert any(
        "docx" in row[2].lower()
        and "pptx" in row[2].lower()
        and "xlsx" in row[2].lower()
        for row in rows
    )
    assert any("markdown" in row[1].lower() and "zip" in row[2].lower() for row in rows)
    assert any(".html" in row[0].lower() and "pdf" in row[2].lower() for row in rows)
    assert any(".html" in row[0].lower() and "zip" in row[2].lower() for row in rows)
    assert "100 mb" in content.lower() and "500 mb" in content.lower()


def test_inventory_marks_raw_and_offline_translation_as_implemented():
    inventory = (ROOT / ".specs/features/project-foundation/feature-inventory.md").read_text(
        encoding="utf-8"
    )
    translation = next(
        line for line in inventory.splitlines() if "AI summary / translation" in line
    )
    assert "offline PT-BR/English PDF text translation are implemented" in translation
    assert "machine translation remains planned" not in translation
    raw = next(
        line for line in inventory.splitlines() if "Convert from SVG" in line
    )
    assert "Implemented" in raw
    assert "planned" not in raw.lower()


def _env_file_values() -> dict[str, str]:
    lines = (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
    return dict(line.split("=", 1) for line in lines if line and not line.startswith("#"))


def _documented_configuration(content: str) -> dict[str, str]:
    values = {}
    for line in content.splitlines():
        if not line.startswith("| `"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        values[cells[0].strip("`")] = cells[1].strip().strip("`")
    return values


@pytest.mark.parametrize("filename", READMES)
def test_self_host_documentation_matches_compose_defaults(filename):
    env_values = _env_file_values()
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    compose_values = dict(re.findall(r"\$\{([A-Z_]+):-([^}]+)\}", compose))
    assert compose_values == env_values

    content = (ROOT / filename).read_text(encoding="utf-8")
    assert _documented_configuration(content) == env_values
    assert "docker compose ps" in content
    assert "docker compose logs -f web worker" in content
    assert "docker compose down" in content
    assert "docker compose down -v" not in content
    assert "without deleting its files" in content or "sem apagar os arquivos" in content
    assert "Copy-Item .env.example .env" in content or "cp .env.example .env" in content
