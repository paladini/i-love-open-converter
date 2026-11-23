"""Executable inventory for accepted operations and documented format paths."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from i_love_open_converter.main import SUPPORTED_OPERATIONS
from i_love_open_converter.office_ops import FAMILIES
from i_love_open_converter.raw_ops import RAW_EXTENSIONS

TEST_MODULES = {
    "api": "tests/test_api.py",
    "archive": "tests/test_pdf_archive.py",
    "compression": "tests/test_pdf_compression.py",
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
    "image.convert": ("api", "test_convert_job_moves_from_queued_to_downloadable"),
    "image.from_jpg": ("jpg", "test_single_jpeg_converts_to_png_with_source_dimensions"),
    "image.from_heic": ("heic", "test_heic_api_and_worker_return_one_jpeg_or_a_zip_for_batches"),
    "image.from_raw": ("raw", "test_raw_api_and_worker_return_jpeg_or_zip_for_batches"),
    "image.from_psd": ("psd", "test_psd_conversion_creates_one_bounded_raster_artifact"),
    "image.from_svg": ("api", "test_svg_conversion_job_is_queued_with_bounded_dimensions"),
    "image.resize": ("api", "test_batch_resize_returns_zip_with_aspect_ratio_preserved"),
    "image.compress": ("image_ops", "test_convert_image_writes_requested_format_and_size"),
    "image.rotate": ("api", "test_image_rotate_is_clockwise_and_invalid_dimensions_are_rejected"),
    "image.meme": ("api", "test_meme_generator_creates_local_jpeg_and_rejects_invalid_requests"),
    "image.upscale": ("api", "test_upscale_job_uses_selected_scale_and_rejects_bad_options"),
    "image.remove_background": (
        "api",
        "test_background_removal_creates_transparent_png_and_rejects_other_formats",
    ),
    "image.blur_faces": ("api", "test_face_blur_no_faces_fails_without_downloadable_output"),
    "image.blur_plates": ("api", "test_plate_blur_no_detection_fails_without_downloadable_output"),
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
    "pdf.compress": ("compression", "test_single_pdf_compression_keeps_pdf_download_shape"),
    "pdf.to_image": ("api", "test_pdf_range_validation_rotation_and_pdf_to_jpg"),
    "pdf.extract_images": ("api", "test_extract_images_deduplicates_and_preserves_transparency"),
    "pdf.to_markdown": ("markdown", "test_pdf_to_markdown_packages_text_and_images"),
    "pdf.to_word": ("word", "test_pdf_to_word_has_editable_text_in_order"),
    "pdf.to_powerpoint": (
        "powerpoint",
        "test_pdf_to_powerpoint_creates_editable_text_and_picture_shapes",
    ),
    "pdf.to_excel": ("excel", "test_pdf_to_excel_extracts_tables_and_text_as_literal_strings"),
    "html.to_pdf": ("html_pdf", "test_html_to_pdf_creates_pdf_artifact_and_downloads_it"),
    "html.to_image": (
        "html_image",
        "test_html_to_image_captures_public_url_and_queues_requested_format",
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


def test_operation_matrix_matches_the_api_contract_and_existing_tests():
    assert set(OPERATION_CASES) == SUPPORTED_OPERATIONS

    for operation, (module, test_name) in OPERATION_CASES.items():
        filename = TEST_MODULES[module]
        source = (ROOT / filename).read_text(encoding="utf-8")
        assert re.search(rf"^def {re.escape(test_name)}\s*\(", source, re.MULTILINE), operation


def test_active_home_catalog_tools_map_to_supported_operations():
    template = (ROOT / "src/i_love_open_converter/templates/index.html").read_text(encoding="utf-8")
    catalog_operations = set(re.findall(r'data-tool="([a-z0-9_.]+)"', template))
    assert catalog_operations <= set(OPERATION_CASES)

    catalog_routes = set(re.findall(r'href="/tools/([^"]+)"', template))
    mapped_operations = set().union(*(PDF_TOOL_ROUTES[route] for route in catalog_routes))
    assert mapped_operations <= set(OPERATION_CASES)


def test_format_pair_matrix_has_an_operation_case_and_documentation_row():
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
