"""Executable inventory for accepted operations and documented format paths."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import unicodedata
from io import BytesIO
from itertools import product
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZIP_DEFLATED, ZipFile

import pymupdf
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from i_love_open_converter.main import SUPPORTED_OPERATIONS, create_app
from i_love_open_converter.office_ops import FAMILIES
from i_love_open_converter.raw_ops import RAW_EXTENSIONS
from i_love_open_converter.worker import process_one_job

TEST_MODULES = {
    "api": "tests/test_api.py",
    "archive": "tests/test_pdf_archive.py",
    "compression": "tests/test_pdf_compression.py",
    "coverage": "tests/test_conversion_coverage.py",
    "editor": "tests/test_image_editor.py",
    "excel": "tests/test_pdf_to_excel.py",
    "heic": "tests/test_heic_ops.py",
    "html_image": "tests/test_html_to_image.py",
    "html_pdf": "tests/test_html_to_pdf.py",
    "image_crop": "tests/test_image_crop.py",
    "image_ops": "tests/test_image_ops.py",
    "image_watermark": "tests/test_image_watermark.py",
    "jpg": "tests/test_image_from_jpg.py",
    "markdown": "tests/test_markdown.py",
    "office": "tests/test_office.py",
    "powerpoint": "tests/test_pdf_to_powerpoint.py",
    "psd": "tests/test_psd_ops.py",
    "raw": "tests/test_raw_ops.py",
    "word": "tests/test_pdf_to_word.py",
}

OPERATION_CASES = {
    "image.convert": (
        "coverage",
        "test_generic_raster_pair_runs_through_job_and_returns_valid_image",
    ),
    "image.from_jpg": ("coverage", "test_jpeg_conversion_matrix_runs_through_job_and_download"),
    "image.from_heic": ("coverage", "test_heic_extension_matrix_runs_through_job_and_download"),
    "image.from_raw": ("coverage", "test_raw_extension_matrix_runs_through_job_and_download"),
    "image.from_psd": ("psd", "test_psd_conversion_creates_one_bounded_raster_artifact"),
    "image.from_svg": (
        "coverage",
        "test_svg_format_matrix_runs_through_job_and_returns_valid_image",
    ),
    "image.resize": ("api", "test_batch_resize_returns_zip_with_aspect_ratio_preserved"),
    "image.compress": ("coverage", "test_image_batch_operations_return_valid_zip_entries"),
    "image.rotate": ("coverage", "test_image_batch_operations_return_valid_zip_entries"),
    "image.meme": ("api", "test_meme_generator_creates_local_jpeg_and_rejects_invalid_requests"),
    "image.upscale": ("api", "test_upscale_job_uses_selected_scale_and_rejects_bad_options"),
    "image.remove_background": (
        "api",
        "test_background_removal_creates_transparent_png_and_rejects_other_formats",
    ),
    "image.blur_faces": ("coverage", "test_privacy_blur_success_runs_through_job_and_download"),
    "image.blur_plates": ("coverage", "test_privacy_blur_success_runs_through_job_and_download"),
    "image.blur_regions": ("api", "test_blur_tools_are_listed_and_manual_regions_process"),
    "image.editor": ("editor", "test_editor_returns_selected_output_format"),
    "image.crop": ("image_crop", "test_single_crop_downloads_one_sanitized_image"),
    "image.watermark": (
        "image_watermark",
        "test_text_watermark_is_applied_at_selected_position_and_opacity",
    ),
    "image.to_pdf": ("api", "test_static_images_become_a4_pdf_and_invalid_pdf_is_rejected"),
    "pdf.merge": ("api", "test_pdf_merge_and_page_range_split"),
    "pdf.split": ("api", "test_pdf_merge_and_page_range_split"),
    "pdf.rotate": ("api", "test_pdf_range_validation_rotation_and_pdf_to_jpg"),
    "pdf.compress": (
        "compression",
        "test_batch_pdf_compression_returns_ordered_zip_with_unique_names",
    ),
    "pdf.to_image": ("api", "test_pdf_range_validation_rotation_and_pdf_to_jpg"),
    "pdf.extract_images": ("api", "test_extract_images_deduplicates_and_preserves_transparency"),
    "pdf.to_markdown": ("markdown", "test_pdf_to_markdown_packages_text_and_images"),
    "pdf.to_word": ("word", "test_pdf_to_word_has_editable_text_in_order"),
    "pdf.to_powerpoint": (
        "powerpoint",
        "test_pdf_to_powerpoint_creates_editable_text_and_picture_shapes",
    ),
    "pdf.to_excel": ("excel", "test_pdf_to_excel_extracts_tables_and_text_as_literal_strings"),
    "html.to_pdf": (
        "coverage",
        "test_html_pdf_input_matrix_runs_through_job_and_download",
    ),
    "html.to_image": (
        "coverage",
        "test_html_image_input_format_matrix_runs_through_job_and_download",
    ),
    "pdf.watermark": ("api", "test_pdf_text_watermark_and_page_numbers_apply_to_every_page"),
    "pdf.page_numbers": ("api", "test_pdf_text_watermark_and_page_numbers_apply_to_every_page"),
    "pdf.organize": ("api", "test_organize_pdf_pages_and_reject_invalid_selection"),
    "pdf.crop": ("api", "test_crop_preserves_unselected_pages_and_respects_rotation"),
    "pdf.edit": ("api", "test_pdf_edit_adds_requested_content"),
    "pdf.sign": ("api", "test_visual_signature_adds_an_image_to_selected_page"),
    "pdf.protect": (
        "api",
        "test_password_protection_and_unlock_do_not_store_password_in_job_options",
    ),
    "pdf.unlock": (
        "api",
        "test_password_protection_and_unlock_do_not_store_password_in_job_options",
    ),
    "pdf.redact": (
        "api",
        "test_redaction_blanks_image_pixels_and_removes_overlapping_annotations",
    ),
    "pdf.forms": ("api", "test_form_fields_are_listed_filled_and_unsupported_rejected"),
    "pdf.repair": ("api", "test_pdf_repair_recovers_cross_reference_and_handles_unreadable_file"),
    "pdf.compare": ("api", "test_pdf_compare_reports_changed_added_and_removed_pages"),
    "pdf.pdfa": ("archive", "test_pdfa_is_unavailable_without_installed_dependencies"),
    "pdf.ocr": ("api", "test_pdf_ocr_creates_searchable_download_with_selected_language"),
    "pdf.summary": (
        "api",
        "test_pdf_summary_is_extractive_ordered_and_limited_to_twelve_sentences",
    ),
    "pdf.translate": ("api", "test_pdf_translation_job_returns_text_pdf_download"),
    **{family: ("office", "test_office_job_and_download") for family in FAMILIES},
}

RASTER_INPUTS = ("JPEG", "PNG", "static GIF", "WebP", "BMP", "TIFF")
GENERIC_RASTER_OUTPUTS = ("JPEG", "PNG", "WebP", "static GIF")
RAW_INPUTS = tuple(sorted(RAW_EXTENSIONS))

# (operation, input format, output format, README table row)
FORMAT_PAIRS = tuple(
    [
        ("image.convert", source, target, 0)
        for source in RASTER_INPUTS
        for target in GENERIC_RASTER_OUTPUTS
    ]
    + [("image.from_jpg", "JPEG", "PNG", 1), ("image.from_jpg", "JPEG batch", "animated GIF", 1)]
    + [("image.from_svg", ".svg", output, 2) for output in ("JPEG", "PNG", "WebP")]
    + [("image.from_psd", ".psd", output, 3) for output in ("JPEG", "PNG", "WebP")]
    + [("image.from_heic", extension, "JPEG", 4) for extension in (".heic", ".heif", ".hif")]
    + [("image.from_raw", extension, "JPEG", 5) for extension in RAW_INPUTS]
    + [
        ("pdf.to_word", "selectable PDF", "DOCX", 7),
        ("pdf.to_powerpoint", "selectable PDF", "PPTX", 7),
        ("pdf.to_excel", "selectable PDF", "XLSX", 7),
        ("pdf.to_word", "scanned PDF with OCR", "DOCX", 8),
        ("pdf.to_excel", "scanned PDF with OCR", "XLSX", 8),
        ("pdf.to_markdown", "PDF", "ZIP", 9),
        ("pdf.extract_images", "PDF", "ZIP", 9),
    ]
    + [
        (family, extension, "PDF", 10)
        for family, extensions in FAMILIES.items()
        for extension in sorted(extensions)
    ]
    + [("html.to_pdf", extension, "PDF", 11) for extension in (".html", ".htm", "public URL")]
    + [
        ("html.to_image", extension, f"ZIP of {image_format}", 12)
        for extension in (".html", ".htm", "public URL")
        for image_format in ("JPG", "SVG")
    ]
)

DOCUMENTATION_ROWS = (
    (("jpeg", "png", "gif", "webp", "bmp", "tiff"), ("jpeg", "png", "webp", "gif")),
    (("jpeg",), ("png", "gif")),
    (("svg",), ("jpeg", "png", "webp")),
    (("psd",), ("jpeg", "png", "webp")),
    (("heic", "heif", "hif"), ("jpeg",)),
    ((".3fr", ".cr3", ".srw"), ("jpeg",)),
    (("pdf",), ("pdf",)),
    (("pdf",), ("docx", "pptx", "xlsx")),
    (("pdf",), ("docx", "xlsx")),
    (("pdf",), ("zip",)),
    (("word", "powerpoint", "excel"), ("pdf",)),
    (("html", "url"), ("pdf",)),
    (("html", "url"), ("zip",)),
)

ROOT = Path(__file__).resolve().parents[1]
READMES = {
    "README.md": "Formats and limits",
    "README.pt-BR.md": "Formatos e limites",
}

PDF_TOOL_ROUTES = {
    "pdf-watermark": {"pdf.watermark"},
    "pdf-page-numbers": {"pdf.page_numbers"},
    "pdf-organize": {"pdf.organize"},
    "pdf-crop": {"pdf.crop"},
    "pdf-edit": {"pdf.edit"},
    "pdf-sign": {"pdf.sign"},
    "pdf-redact": {"pdf.redact"},
    "pdf-forms": {"pdf.forms"},
    "pdf-repair": {"pdf.repair"},
    "pdf-extract-images": {"pdf.extract_images"},
    "pdf-to-markdown": {"pdf.to_markdown"},
    "pdf-ocr": {"pdf.ocr"},
    "pdf-summary": {"pdf.summary"},
    "pdf-translate": {"pdf.translate"},
    "scan-to-pdf": {"image.to_pdf"},
    "pdf-to-word": {"pdf.to_word"},
    "pdf-to-powerpoint": {"pdf.to_powerpoint"},
    "pdf-to-excel": {"pdf.to_excel"},
    "html-to-pdf": {"html.to_pdf"},
    "html-to-image": {"html.to_image"},
    "pdf-compare": {"pdf.compare"},
    "pdf-pdfa": {"pdf.pdfa"},
    "pdf-protect": {"pdf.protect"},
    "pdf-unlock": {"pdf.unlock"},
    "office-to-pdf/{{ family }}": set(FAMILIES),
}


def _normalized(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(character for character in decomposed if not unicodedata.combining(character))


def _format_alias(value: str) -> str:
    normalized = _normalized(value)
    if normalized.startswith("zip"):
        return "zip"
    if normalized == "jpeg batch":
        return "jpeg"
    if normalized in {"static gif", "animated gif"}:
        return "gif"
    if normalized in {"selectable pdf", "scanned pdf with ocr"}:
        return "pdf"
    if normalized == "public url":
        return "url"
    if normalized in {".doc", ".docx"}:
        return "word"
    if normalized in {".ppt", ".pptx"}:
        return "powerpoint"
    if normalized in {".xls", ".xlsx"}:
        return "excel"
    if normalized.startswith("."):
        return normalized[1:]
    return normalized


def _readme_rows(filename: str) -> list[list[str]]:
    content = (ROOT / filename).read_text(encoding="utf-8")
    heading = READMES[filename]
    start = content.index(heading)
    end = content.find("\n## ", start + len(heading))
    section = content[start:] if end < 0 else content[start:end]
    rows = [line for line in section.splitlines() if line.startswith("|")]
    return [[cell.strip() for cell in line.strip("|").split("|")] for line in rows[2:]]


def _reachable_test_source(filename: str, test_name: str) -> str:
    module = ast.parse((ROOT / filename).read_text(encoding="utf-8"))
    functions = {
        node.name: node
        for node in ast.walk(module)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    pending = [test_name]
    visited = set()
    excerpts = []
    while pending:
        name = pending.pop()
        if name in visited or name not in functions:
            continue
        visited.add(name)
        node = functions[name]
        excerpts.append(ast.get_source_segment((ROOT / filename).read_text(encoding="utf-8"), node))
        for call in (item for item in ast.walk(node) if isinstance(item, ast.Call)):
            called = call.func.id if isinstance(call.func, ast.Name) else None
            if called in functions and called not in visited:
                pending.append(called)
    return "\n".join(excerpts)


def test_operation_matrix_matches_the_api_contract_and_existing_tests():
    assert set(OPERATION_CASES) == SUPPORTED_OPERATIONS

    for operation, (module, test_name) in OPERATION_CASES.items():
        filename = TEST_MODULES[module]
        source = (ROOT / filename).read_text(encoding="utf-8")
        assert re.search(rf"^def {re.escape(test_name)}\s*\(", source, re.MULTILINE), operation


def test_runtime_heic_fixture_has_pinned_source_and_license_provenance():
    fixture = ROOT / "tests/fixtures/heic/example.heic"
    provenance = (fixture.parent / "README.md").read_text(encoding="utf-8")

    assert "strukturag/libheif` v1.23.7" in provenance
    assert "tests/data/rainbow-451x461.heic" in provenance
    assert "COPYING" in provenance and "LGPL-3.0-or-later" in provenance
    assert hashlib.sha256(fixture.read_bytes()).hexdigest() in provenance


def test_mapped_job_cases_reach_the_worker_and_a_download_assertion():
    for operation, (module, test_name) in OPERATION_CASES.items():
        source = _reachable_test_source(TEST_MODULES[module], test_name)
        if operation == "pdf.pdfa":
            assert "pdfa_is_unavailable_without_installed_dependencies" in source
            continue
        assert "process_one_job(" in source, operation
        assert "download" in source.casefold(), operation


@pytest.mark.parametrize("operation", sorted(SUPPORTED_OPERATIONS))
def test_every_operation_rejects_malformed_upload_before_creating_a_job(settings, operation):
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/jobs",
            data={"operation": operation, "options": "{}"},
            files=[("files", ("empty.bin", b"", "application/octet-stream"))],
        )

    assert response.status_code in {415, 422, 503}, (operation, response.text)
    assert response.json()["error"]["code"] in {
        "invalid_file",
        "invalid_options",
        "service_unavailable",
        "unsupported_format",
    }, operation
    assert list(settings.jobs_dir.iterdir()) == []


def test_active_home_catalog_tools_map_to_supported_operations():
    template = (ROOT / "src/i_love_open_converter/templates/index.html").read_text(encoding="utf-8")
    catalog_operations = set(re.findall(r'data-tool="([a-z0-9_.]+)"', template))
    assert catalog_operations <= set(OPERATION_CASES)

    catalog_routes = set(re.findall(r'href="/tools/([^"]+)"', template))
    mapped_operations = set().union(*(PDF_TOOL_ROUTES[route] for route in catalog_routes))
    assert mapped_operations <= set(OPERATION_CASES)


def test_format_pair_matrix_has_an_operation_case_and_documentation_row():
    expected_generic_pairs = {
        ("image.convert", source, output, 0)
        for source, output in product(RASTER_INPUTS, GENERIC_RASTER_OUTPUTS)
    }
    assert {pair for pair in FORMAT_PAIRS if pair[3] == 0} == expected_generic_pairs

    for operation, input_format, output_format, row_index in FORMAT_PAIRS:
        assert operation in OPERATION_CASES, (operation, input_format, output_format)
        assert 0 <= row_index < len(DOCUMENTATION_ROWS)
        assert input_format and output_format
        input_alias = _format_alias(input_format)
        output_alias = _format_alias(output_format)
        for filename in READMES:
            row = _readme_rows(filename)[row_index]
            assert input_alias in _normalized(row[0]), (operation, input_format, filename)
            assert output_alias in _normalized(row[2]), (operation, output_format, filename)


@pytest.mark.parametrize("source_format", RASTER_INPUTS)
@pytest.mark.parametrize("output_format", GENERIC_RASTER_OUTPUTS)
def test_generic_raster_pair_runs_through_job_and_returns_valid_image(
    settings, source_format, output_format
):
    source_extensions = {
        "JPEG": ".jpg",
        "PNG": ".png",
        "static GIF": ".gif",
        "WebP": ".webp",
        "BMP": ".bmp",
        "TIFF": ".tiff",
    }
    output_names = {"static GIF": "GIF", "WebP": "WEBP"}
    output_mime = {
        "JPEG": "image/jpeg",
        "PNG": "image/png",
        "GIF": "image/gif",
        "WEBP": "image/webp",
    }
    pil_format = {"static GIF": "GIF"}
    source = BytesIO()
    Image.new("RGB", (17, 13), (30, 90, 150)).save(
        source, format=pil_format.get(source_format, source_format.upper())
    )
    filename = f"matrix{source_extensions[source_format]}"
    selected_output = output_names.get(output_format, output_format.upper())
    expected_extension = ".jpg" if selected_output == "JPEG" else f".{selected_output.lower()}"

    with TestClient(create_app(settings)) as client:
        submitted = client.post(
            "/api/jobs",
            data={"operation": "image.convert", "options": f'{{"format":"{selected_output}"}}'},
            files={"files": (filename, source.getvalue(), "application/octet-stream")},
        )
        assert submitted.status_code == 202, submitted.text
        assert process_one_job(settings)
        status_response = client.get(submitted.json()["status_url"])
        assert status_response.status_code == 200
        status = status_response.json()
        assert status["state"] == "succeeded"
        assert status["files"][0]["name"].endswith(expected_extension)
        download = client.get(status["download_url"])

    assert download.status_code == 200
    assert download.headers["content-type"] == output_mime[selected_output]
    with Image.open(BytesIO(download.content)) as result:
        assert result.format == selected_output
        assert result.size == (17, 13)
        if selected_output == "GIF":
            assert result.n_frames == 1


@pytest.mark.parametrize("output_format", ["JPEG", "PNG", "GIF", "WEBP"])
def test_generic_raster_batch_returns_zip_with_valid_entries(settings, output_format):
    files = []
    for name, color in (("first", (20, 80, 140)), ("second", (140, 80, 20))):
        source = BytesIO()
        Image.new("RGB", (16, 12), color).save(source, format="JPEG")
        files.append(("files", (f"{name}.jpg", source.getvalue(), "image/jpeg")))

    extension = ".jpg" if output_format == "JPEG" else f".{output_format.lower()}"
    with TestClient(create_app(settings)) as client:
        submitted = client.post(
            "/api/jobs",
            data={"operation": "image.convert", "options": json.dumps({"format": output_format})},
            files=files,
        )
        assert submitted.status_code == 202, submitted.text
        assert process_one_job(settings)
        status = client.get(submitted.json()["status_url"]).json()
        assert status["state"] == "succeeded"
        download = client.get(status["download_url"])

    assert download.status_code == 200
    assert download.headers["content-type"] == "application/zip"
    with ZipFile(BytesIO(download.content)) as archive:
        assert archive.namelist() == [f"first{extension}", f"second{extension}"]
        for filename in archive.namelist():
            with Image.open(BytesIO(archive.read(filename))) as result:
                assert result.format == output_format
                assert result.size == (16, 12)
                if output_format == "GIF":
                    assert result.n_frames == 1


def test_image_compression_runs_through_job_and_download(settings):
    source = BytesIO()
    Image.new("RGB", (64, 48), (120, 80, 40)).save(source, format="JPEG", quality=95)
    with TestClient(create_app(settings)) as client:
        submitted = client.post(
            "/api/jobs",
            data={
                "operation": "image.compress",
                "options": '{"format":"JPEG","quality":35}',
            },
            files={"files": ("compressed.jpg", source.getvalue(), "image/jpeg")},
        )
        assert submitted.status_code == 202, submitted.text
        assert process_one_job(settings)
        status = client.get(submitted.json()["status_url"]).json()
        assert status["state"] == "succeeded"
        download = client.get(status["download_url"])

    assert download.status_code == 200
    assert download.headers["content-type"] == "image/jpeg"
    with Image.open(BytesIO(download.content)) as result:
        assert result.format == "JPEG"
        assert result.size == (64, 48)


@pytest.mark.parametrize(
    ("operation", "options", "expected_extension", "expected_format", "dimensions"),
    [
        (
            "image.compress",
            {"format": "JPEG", "quality": 35},
            ".jpg",
            "JPEG",
            ((16, 12), (12, 16)),
        ),
        (
            "image.rotate",
            {"degrees": 90, "format": "PNG"},
            ".png",
            "PNG",
            ((12, 16), (16, 12)),
        ),
    ],
)
def test_image_batch_operations_return_valid_zip_entries(
    settings, operation, options, expected_extension, expected_format, dimensions
):
    files = []
    for name, size, color in (
        ("first", (16, 12), (10, 50, 90)),
        ("second", (12, 16), (90, 50, 10)),
    ):
        source = BytesIO()
        Image.new("RGB", size, color).save(source, format="JPEG")
        files.append(("files", (f"{name}.jpg", source.getvalue(), "image/jpeg")))

    with TestClient(create_app(settings)) as client:
        submitted = client.post(
            "/api/jobs",
            data={"operation": operation, "options": json.dumps(options)},
            files=files,
        )
        assert submitted.status_code == 202, submitted.text
        assert process_one_job(settings)
        status = client.get(submitted.json()["status_url"]).json()
        assert status["state"] == "succeeded"
        download = client.get(status["download_url"])

    assert download.status_code == 200
    assert download.headers["content-type"] == "application/zip"
    with ZipFile(BytesIO(download.content)) as archive:
        assert archive.namelist() == [f"first{expected_extension}", f"second{expected_extension}"]
        for filename, expected_size in zip(archive.namelist(), dimensions, strict=True):
            with Image.open(BytesIO(archive.read(filename))) as result:
                assert result.format == expected_format
                assert result.size == expected_size


@pytest.mark.parametrize(
    ("extensions", "output_format", "frame_count"),
    [([".jpg"], "PNG", 1), ([".jpeg"], "PNG", 1), ([".jpg", ".jpeg"], "GIF", 2)],
)
def test_jpeg_conversion_matrix_runs_through_job_and_download(
    settings, extensions, output_format, frame_count
):
    files = []
    for index, extension in enumerate(extensions):
        image = BytesIO()
        Image.new("RGB", (16, 12), (50 + index * 50, 80, 120)).save(image, format="JPEG")
        files.append(("files", (f"frame{index}{extension}", image.getvalue(), "image/jpeg")))
    with TestClient(create_app(settings)) as client:
        submitted = client.post(
            "/api/jobs",
            data={"operation": "image.from_jpg", "options": f'{{"format":"{output_format}"}}'},
            files=files,
        )
        assert submitted.status_code == 202, submitted.text
        assert process_one_job(settings)
        status = client.get(submitted.json()["status_url"]).json()
        assert status["state"] == "succeeded"
        download = client.get(status["download_url"])

    expected_format = output_format
    expected_mime = {"PNG": "image/png", "GIF": "image/gif"}[expected_format]
    assert download.status_code == 200
    assert download.headers["content-type"] == expected_mime
    with Image.open(BytesIO(download.content)) as result:
        assert result.format == expected_format
        assert result.size == (16, 12)
        assert getattr(result, "n_frames", 1) == frame_count


@pytest.mark.parametrize("extension", [".heic", ".heif", ".hif"])
def test_heic_extension_matrix_runs_through_job_and_download(settings, monkeypatch, extension):
    from i_love_open_converter import worker

    jpeg = BytesIO()
    Image.new("RGB", (18, 14), (90, 40, 20)).save(jpeg, format="JPEG")
    jpeg_bytes = jpeg.getvalue()

    def decode_heic(_source, destination, image_format):
        assert image_format == "JPEG"
        destination.write_bytes(jpeg_bytes)
        return "image/jpeg", len(jpeg_bytes)

    monkeypatch.setattr(worker, "convert_heic_to_image", decode_heic)
    brand = {".heic": b"heic", ".heif": b"heif", ".hif": b"mif1"}[extension]
    payload = brand + bytes(4)
    heic_bytes = (8 + len(payload)).to_bytes(4, "big") + b"ftyp" + payload
    with TestClient(create_app(settings)) as client:
        submitted = client.post(
            "/api/jobs",
            data={"operation": "image.from_heic", "options": '{"format":"JPEG"}'},
            files={"files": (f"photo{extension}", heic_bytes, "application/octet-stream")},
        )
        assert submitted.status_code == 202, submitted.text
        assert process_one_job(settings)
        status = client.get(submitted.json()["status_url"]).json()
        assert status["state"] == "succeeded"
        download = client.get(status["download_url"])

    assert download.status_code == 200
    assert download.headers["content-type"] == "image/jpeg"
    with Image.open(BytesIO(download.content)) as result:
        assert result.format == "JPEG"
        assert result.size == (18, 14)


@pytest.mark.parametrize("extension", RAW_INPUTS)
def test_raw_extension_matrix_runs_through_job_and_download(settings, monkeypatch, extension):
    from i_love_open_converter import worker

    jpeg = BytesIO()
    Image.new("RGB", (18, 14), (90, 40, 20)).save(jpeg, format="JPEG")
    jpeg_bytes = jpeg.getvalue()

    def decode_raw(_source, destination, image_format):
        assert image_format == "JPEG"
        destination.write_bytes(jpeg_bytes)
        return "image/jpeg", len(jpeg_bytes)

    monkeypatch.setattr(worker, "convert_raw_to_jpeg", decode_raw)
    with TestClient(create_app(settings)) as client:
        submitted = client.post(
            "/api/jobs",
            data={"operation": "image.from_raw", "options": '{"format":"JPEG"}'},
            files={
                "files": (f"camera{extension}", b"raw camera fixture", "application/octet-stream")
            },
        )
        assert submitted.status_code == 202, submitted.text
        assert process_one_job(settings)
        status = client.get(submitted.json()["status_url"]).json()
        assert status["state"] == "succeeded"
        download = client.get(status["download_url"])

    assert download.status_code == 200
    assert download.headers["content-type"] == "image/jpeg"
    with Image.open(BytesIO(download.content)) as result:
        assert result.format == "JPEG"
        assert result.size == (18, 14)


@pytest.mark.parametrize(
    ("operation", "detector_name"),
    [
        ("image.blur_faces", "_detect_face_regions"),
        ("image.blur_plates", "_detect_plate_regions"),
    ],
)
def test_privacy_blur_success_runs_through_job_and_download(
    settings, monkeypatch, operation, detector_name
):
    from i_love_open_converter import image_ops

    monkeypatch.setattr(image_ops, detector_name, lambda _image: [(30, 20, 50, 40)])
    source = BytesIO()
    image = Image.new("RGB", (100, 80), "white")
    image.paste((0, 0, 0), (30, 20, 50, 40))
    image.save(source, format="JPEG")
    with TestClient(create_app(settings)) as client:
        submitted = client.post(
            "/api/jobs",
            data={"operation": operation, "options": '{"format":"PNG"}'},
            files={"files": ("privacy.jpg", source.getvalue(), "image/jpeg")},
        )
        assert submitted.status_code == 202, submitted.text
        assert process_one_job(settings)
        status = client.get(submitted.json()["status_url"]).json()
        assert status["state"] == "succeeded"
        download = client.get(status["download_url"])

    assert download.status_code == 200
    assert download.headers["content-type"] == "image/png"
    with Image.open(BytesIO(download.content)) as result:
        assert result.format == "PNG"
        assert result.size == (100, 80)


@pytest.mark.parametrize("output_format", ["PNG", "JPEG", "WEBP"])
def test_svg_format_matrix_runs_through_job_and_returns_valid_image(
    settings, monkeypatch, output_format
):
    from i_love_open_converter import worker

    mime_types = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}

    def render_svg(source, destination, image_format, width, height):
        assert source.read_bytes().startswith(b"<svg")
        assert (width, height) == (640, 480)
        Image.new("RGB", (width, height), (20, 80, 140)).save(destination, image_format)
        return mime_types[image_format], destination.stat().st_size

    monkeypatch.setattr(worker, "convert_svg_to_image", render_svg)
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 480"/>'
    with TestClient(create_app(settings)) as client:
        submitted = client.post(
            "/api/jobs",
            data={"operation": "image.from_svg", "options": f'{{"format":"{output_format}"}}'},
            files={"files": ("drawing.svg", svg, "image/svg+xml")},
        )
        assert submitted.status_code == 202, submitted.text
        assert process_one_job(settings)
        status = client.get(submitted.json()["status_url"]).json()
        assert status["state"] == "succeeded"
        download = client.get(status["download_url"])

    assert download.status_code == 200
    assert download.headers["content-type"] == mime_types[output_format]
    with Image.open(BytesIO(download.content)) as result:
        assert result.format == output_format
        assert result.size == (640, 480)


@pytest.mark.parametrize("source_mode", [".html", ".htm", "public URL"])
@pytest.mark.parametrize("image_format", ["jpg", "svg"])
def test_html_image_input_format_matrix_runs_through_job_and_download(
    settings, monkeypatch, source_mode, image_format
):
    from i_love_open_converter import main as main_module
    from i_love_open_converter import pdf_ops

    fetched_urls = []

    def render_html(_source, output_dir, selected_format):
        assert selected_format == image_format
        output_dir.mkdir(parents=True, exist_ok=True)
        destination = output_dir / "converted-images.zip"
        with ZipFile(destination, "w", ZIP_DEFLATED) as archive:
            if selected_format == "jpg":
                image = BytesIO()
                Image.new("RGB", (20, 12), (60, 30, 120)).save(image, format="JPEG")
                archive.writestr("page-001.jpg", image.getvalue())
            else:
                archive.writestr(
                    "page-001.svg",
                    b'<svg xmlns="http://www.w3.org/2000/svg" width="20" height="12"/>',
                )
        return destination

    monkeypatch.setattr(pdf_ops, "convert_html_to_images", render_html)
    data = {"operation": "html.to_image", "options": json.dumps({"format": image_format})}
    if source_mode == "public URL":
        url = "https://public.example/matrix"
        data["url"] = url
        files = {"multipart-marker": ("marker.txt", b"x", "text/plain")}
        monkeypatch.setattr(
            main_module,
            "fetch_public_html",
            lambda value: fetched_urls.append(value) or b"<h1>URL</h1>",
        )
    else:
        url = None
        files = {"files": (f"matrix{source_mode}", b"<h1>Local HTML</h1>", "text/html")}

    with TestClient(create_app(settings)) as client:
        submitted = client.post("/api/jobs", data=data, files=files)
        assert submitted.status_code == 202, submitted.text
        assert process_one_job(settings)
        status = client.get(submitted.json()["status_url"]).json()
        assert status["state"] == "succeeded"
        download = client.get(status["download_url"])

    assert download.status_code == 200
    assert download.headers["content-type"] == "application/zip"
    if url is not None:
        assert fetched_urls == [url]
    with ZipFile(BytesIO(download.content)) as archive:
        assert archive.namelist() == [f"page-001.{image_format}"]
        member = archive.read(archive.namelist()[0])
    if image_format == "jpg":
        with Image.open(BytesIO(member)) as result:
            assert result.format == "JPEG"
            assert result.size == (20, 12)
    else:
        assert ElementTree.fromstring(member).tag.endswith("svg")


@pytest.mark.parametrize("source_mode", [".html", ".htm", "public URL"])
def test_html_pdf_input_matrix_runs_through_job_and_download(settings, monkeypatch, source_mode):
    from i_love_open_converter import main as main_module
    from i_love_open_converter import pdf_ops

    fetched_urls = []

    def render_html(_source, output_dir):
        output_dir.mkdir(parents=True, exist_ok=True)
        destination = output_dir / "converted.pdf"
        document = pymupdf.open()
        page = document.new_page()
        page.insert_text((30, 40), "Rendered HTML")
        document.save(destination)
        document.close()
        return destination

    monkeypatch.setattr(pdf_ops, "convert_html", render_html)
    data = {"operation": "html.to_pdf"}
    if source_mode == "public URL":
        url = "https://public.example/matrix"
        data["url"] = url
        files = {"multipart-marker": ("marker.txt", b"x", "text/plain")}
        monkeypatch.setattr(
            main_module,
            "fetch_public_html",
            lambda value: fetched_urls.append(value) or b"<h1>URL</h1>",
        )
    else:
        url = None
        files = {"files": (f"matrix{source_mode}", b"<h1>Local HTML</h1>", "text/html")}

    with TestClient(create_app(settings)) as client:
        submitted = client.post("/api/jobs", data=data, files=files)
        assert submitted.status_code == 202, submitted.text
        assert process_one_job(settings)
        status = client.get(submitted.json()["status_url"]).json()
        assert status["state"] == "succeeded"
        download = client.get(status["download_url"])

    assert download.status_code == 200
    assert download.headers["content-type"] == "application/pdf"
    if url is not None:
        assert fetched_urls == [url]
    with pymupdf.open(stream=download.content, filetype="pdf") as document:
        assert document.page_count == 1
        assert "Rendered HTML" in document[0].get_text()


def test_bilingual_format_tables_cover_every_documented_matrix_row():
    for filename in READMES:
        rows = _readme_rows(filename)
        assert len(rows) == len(DOCUMENTATION_ROWS), filename

        for row_index, (inputs, outputs) in enumerate(DOCUMENTATION_ROWS):
            input_text = _normalized(rows[row_index][0])
            output_text = _normalized(rows[row_index][2])
            assert all(_normalized(token) in input_text for token in inputs), (filename, row_index)
            assert all(_normalized(token) in output_text for token in outputs), (
                filename,
                row_index,
            )

        raw_extensions = set(re.findall(r"\.[a-z0-9]+", rows[5][0].casefold()))
        assert raw_extensions == RAW_EXTENSIONS, filename
