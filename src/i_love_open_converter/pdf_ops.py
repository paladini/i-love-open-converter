from __future__ import annotations

import base64
import hashlib
import html
import os
import re
import socket
import subprocess
import sys
import tempfile
import zipfile
from difflib import SequenceMatcher
from io import BytesIO
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import pymupdf
from PIL import Image, ImageChops, ImageDraw, ImageOps

from .ocr_ops import NoOcrTextError, OcrProcessingError, make_searchable_pdf
from .pdf_archive import convert_pdfa
from .pdf_image_order import image_order


class InvalidPdfError(Exception):
    """The input is not a readable, unencrypted PDF."""


class NoEmbeddedImagesError(Exception):
    """The PDF has no extractable embedded images."""


class MarkdownConversionError(Exception):
    """Markdown processing failed or exceeded a resource limit."""


class WordConversionError(Exception):
    """DOCX processing failed or exceeded a resource limit."""


class WordUnavailableError(WordConversionError):
    """The required Linux network isolation is unavailable."""


class PowerPointConversionError(Exception):
    """PPTX processing failed or exceeded a resource limit."""


class PowerPointUnavailableError(PowerPointConversionError):
    """The required Linux network isolation is unavailable."""


class ExcelConversionError(Exception):
    """XLSX processing failed or exceeded a resource limit."""


class ExcelUnavailableError(ExcelConversionError):
    """The required Linux network isolation is unavailable."""


class NoSpreadsheetDataError(ExcelConversionError):
    """The PDF contains no detected table cells or selectable text."""


def word_isolated() -> bool:
    if sys.platform != "linux" or os.environ.get("OFFICE_NETWORK_ISOLATED") != "1":
        return False
    try:
        return {name for _, name in socket.if_nameindex()} == {"lo"}
    except OSError:
        return False


EDIT_FONTS = {"helv": "DejaVuSans.ttf", "tiro": "DejaVuSerif.ttf", "cour": "DejaVuSansMono.ttf"}
FONT_DIR = Path(__file__).resolve().parent / "static" / "fonts"


def compare_pdfs(sources: list[tuple[Path, str]], output_dir: Path, language: str) -> Path:
    if len(sources) != 2:
        raise InvalidPdfError
    labels = {
        "pt-BR": {
            "title": "Comparação de PDFs",
            "same": "Sem alteração",
            "changed": "Alterada",
            "added": "Adicionada",
            "removed": "Removida",
            "page": "Página",
            "empty": "Sem página correspondente",
            "scope": (
                "Comparação visual com até 1000 pixels por lado; metadados, campos e conteúdo "
                "não visível não são comparados. Detalhes pequenos podem passar despercebidos."
            ),
        },
        "en": {
            "title": "PDF comparison",
            "same": "Unchanged",
            "changed": "Changed",
            "added": "Added",
            "removed": "Removed",
            "page": "Page",
            "empty": "No corresponding page",
            "scope": (
                "Visual comparison at up to 1000 pixels per side; metadata, fields and invisible "
                "content are not compared. Small details may be missed."
            ),
        },
    }[language]
    try:
        with tempfile.TemporaryDirectory(dir=output_dir) as directory:
            rendered: list[list[tuple[str, Path]]] = [[], []]
            for side, (source, _) in enumerate(sources):
                with _open_pdf(source) as document:
                    for number, page in enumerate(document):
                        scale = min(1.0, 1000 / max(page.rect.width, page.rect.height))
                        pixmap = page.get_pixmap(
                            matrix=pymupdf.Matrix(scale, scale),
                            colorspace=pymupdf.csRGB,
                            alpha=False,
                        )
                        pixels = pixmap.tobytes("png")
                        path = Path(directory) / f"{side}-{number}.png"
                        path.write_bytes(pixels)
                        rendered[side].append((hashlib.sha256(pixels).hexdigest(), path))
            left, right = rendered
            matcher = SequenceMatcher(
                None, [x[0] for x in left], [x[0] for x in right], autojunk=False
            )
            rows: list[tuple[str, int | None, int | None]] = []
            for tag, a0, a1, b0, b1 in matcher.get_opcodes():
                if tag == "equal":
                    rows.extend(
                        ("same", a, b) for a, b in zip(range(a0, a1), range(b0, b1), strict=True)
                    )
                elif tag == "replace":
                    paired = min(a1 - a0, b1 - b0)
                    rows.extend(("changed", a0 + i, b0 + i) for i in range(paired))
                    rows.extend(("removed", a, None) for a in range(a0 + paired, a1))
                    rows.extend(("added", None, b) for b in range(b0 + paired, b1))
                elif tag == "delete":
                    rows.extend(("removed", a, None) for a in range(a0, a1))
                else:
                    rows.extend(("added", None, b) for b in range(b0, b1))
            counts = {
                key: sum(1 for kind, _, _ in rows if kind == key)
                for key in ("same", "changed", "added", "removed")
            }
            destination = output_dir / "comparison.html"
            with destination.open("w", encoding="utf-8") as report:
                report.write(
                    '<!doctype html><html lang="'
                    + html.escape(language)
                    + '"><meta charset="utf-8"><meta name="viewport" '
                    + 'content="width=device-width,initial-scale=1">'
                    + '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
                    + "img-src data:; style-src 'unsafe-inline'\"><title>"
                    + labels["title"]
                    + "</title><style>body{font:16px sans-serif;max-width:1200px;"
                    + "margin:auto;padding:1rem}"
                    + "section{border-top:1px solid #ccc;padding:1rem 0}.pair{display:grid;"
                    + "grid-template-columns:1fr 1fr;gap:1rem}"
                    + "img{max-width:100%;border:1px solid #ddd}"
                    + "@media(max-width:600px){.pair{grid-template-columns:1fr}}</style><h1>"
                    + labels["title"]
                    + "</h1>"
                )
                report.write(
                    '<p id="summary">'
                    + " · ".join(f"{labels[key]}: {value}" for key, value in counts.items())
                    + "</p>"
                )
                report.write("<p>" + labels["scope"] + "</p>")
                report.write(
                    "<p>" + html.escape(sources[0][1]) + " → " + html.escape(sources[1][1]) + "</p>"
                )
                for kind, first, second in rows:
                    report.write("<section><h2>" + labels[kind] + '</h2><div class="pair">')
                    difference = None
                    if kind == "changed" and first is not None and second is not None:
                        with (
                            Image.open(left[first][1]) as before,
                            Image.open(right[second][1]) as after,
                        ):
                            if before.size == after.size:
                                difference = ImageChops.difference(before, after).getbbox()
                    for side, index in enumerate((first, second)):
                        if index is None:
                            report.write("<div>" + labels["empty"] + "</div>")
                        else:
                            path = rendered[side][index][1]
                            if difference:
                                with Image.open(path) as original:
                                    marked = original.copy()
                                    ImageDraw.Draw(marked).rectangle(
                                        difference, outline="red", width=2
                                    )
                                    buffer = BytesIO()
                                    marked.save(buffer, format="PNG")
                                    image_bytes = buffer.getvalue()
                            else:
                                image_bytes = path.read_bytes()
                            image = base64.b64encode(image_bytes).decode("ascii")
                            report.write(
                                f"<div><p>{labels['page']} {index + 1}</p>"
                                f'<img alt="{labels["page"]} {index + 1}" '
                                f'src="data:image/png;base64,{image}"></div>'
                            )
                    report.write("</div></section>")
                report.write("</html>")
        return destination
    except InvalidPdfError:
        raise
    except Exception as exc:
        raise InvalidPdfError from exc


def validate_crop_options(options: dict[str, Any], page_count: int) -> list[int]:
    rectangle = options.get("rectangle")
    if (
        not isinstance(rectangle, list)
        or len(rectangle) != 4
        or any(type(value) not in (int, float) or not 0 <= value <= 1 for value in rectangle)
    ):
        raise InvalidPdfError
    x0, y0, x1, y1 = rectangle
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        raise InvalidPdfError
    ranges = options.get("ranges")
    if not isinstance(ranges, str):
        raise InvalidPdfError
    return [
        page
        for first, last in validate_page_ranges(ranges, page_count)
        for page in range(first, last + 1)
    ]


def crop_page(page: pymupdf.Page, rectangle: list[float]) -> None:
    visible = page.rect
    x0, y0, x1, y1 = rectangle
    selected = pymupdf.Rect(
        x0 * visible.width, y0 * visible.height, x1 * visible.width, y1 * visible.height
    )
    unrotated = selected * page.derotation_matrix
    origin = page.cropbox_position
    unrotated += (origin.x, origin.y, origin.x, origin.y)
    page.set_cropbox(unrotated)


def validate_redactions(options: dict[str, Any], page_count: int) -> None:
    regions = options.get("regions")
    if not isinstance(regions, list) or not 1 <= len(regions) <= 100:
        raise InvalidPdfError
    for region in regions:
        if not isinstance(region, dict) or type(region.get("page")) is not int:
            raise InvalidPdfError
        page = region["page"]
        if not 1 <= page <= page_count:
            raise InvalidPdfError
        validate_crop_options(
            {"rectangle": region.get("rectangle"), "ranges": str(page)}, page_count
        )


def _reject_accessibility_text(document) -> None:
    """Fail closed when PDF accessibility structures could retain redacted content."""
    forbidden = re.compile(rb"/(?:ActualText|Alt|StructTreeRoot)\b")

    def contains_forbidden(data: bytes) -> bool:
        decoded = re.sub(rb"#([0-9a-fA-F]{2})", lambda match: bytes([int(match[1], 16)]), data)
        return bool(forbidden.search(decoded))

    for xref in range(1, document.xref_length()):
        if contains_forbidden(document.xref_object(xref).encode("utf-8")):
            raise InvalidPdfError("Accessibility content requires a different redaction method")
        if document.xref_is_stream(xref):
            subtype = document.xref_get_key(xref, "Subtype")
            if subtype == ("name", "/Image"):
                continue
            stream = document.xref_stream(xref) or b""
            if contains_forbidden(stream) or re.search(
                rb"(?<![A-Za-z])(?:BDC|BMC)(?![A-Za-z])", stream
            ):
                raise InvalidPdfError("Accessibility content requires a different redaction method")


def redact_pages(document, options: dict[str, Any]) -> None:
    validate_redactions(options, document.page_count)
    _reject_accessibility_text(document)
    areas: dict[int, list[pymupdf.Rect]] = {}
    for region in options["regions"]:
        number = region["page"] - 1
        page = document[number]
        x0, y0, x1, y1 = region["rectangle"]
        rectangle = (
            pymupdf.Rect(
                x0 * page.rect.width,
                y0 * page.rect.height,
                x1 * page.rect.width,
                y1 * page.rect.height,
            )
            * page.derotation_matrix
        )
        areas.setdefault(number, []).append(rectangle)
    for number, rectangles in areas.items():
        page = document[number]
        annotations = list(page.annots() or [])
        if any(annotation.type[0] == pymupdf.PDF_ANNOT_REDACT for annotation in annotations):
            raise InvalidPdfError("PDF contains pending redactions")
        for annotation in annotations:
            if any(annotation.rect.intersects(rectangle) for rectangle in rectangles):
                page.delete_annot(annotation)
        for widget in list(page.widgets() or []):
            if any(widget.rect.intersects(rectangle) for rectangle in rectangles):
                page.delete_widget(widget)
        for rectangle in rectangles:
            page.add_redact_annot(rectangle, fill=(0, 0, 0), cross_out=False)
        page.apply_redactions(
            images=pymupdf.PDF_REDACT_IMAGE_PIXELS,
            graphics=pymupdf.PDF_REDACT_LINE_ART_REMOVE_IF_TOUCHED,
            text=pymupdf.PDF_REDACT_TEXT_REMOVE,
        )


def list_form_fields(document) -> list[dict[str, Any]]:
    fields = []
    for page_number in range(document.page_count):
        page = document[page_number]
        for widget in page.widgets() or []:
            field_type = {
                pymupdf.PDF_WIDGET_TYPE_TEXT: "text",
                pymupdf.PDF_WIDGET_TYPE_CHECKBOX: "checkbox",
            }.get(widget.field_type, "unsupported")
            if widget.field_flags & pymupdf.PDF_FIELD_IS_READ_ONLY:
                field_type = "unsupported"
            value = widget.field_value
            if field_type == "checkbox":
                value = value not in (None, "", "Off", False, 0)
            elif field_type == "text":
                value = str(value or "")
            else:
                value = None
            fields.append(
                {
                    "page": page_number + 1,
                    "id": widget.xref,
                    "name": widget.field_label or widget.field_name or f"Field {widget.xref}",
                    "type": field_type,
                    "value": value,
                    "multiline": bool(
                        field_type == "text"
                        and widget.field_flags & pymupdf.PDF_TX_FIELD_IS_MULTILINE
                    ),
                    "max_length": widget.text_maxlen if field_type == "text" else 0,
                }
            )
    return fields


def validate_form_updates(document, updates: Any) -> None:
    if not isinstance(updates, list) or len(updates) > 500:
        raise InvalidPdfError
    fields = {field["id"]: field for field in list_form_fields(document)}
    seen = set()
    for update in updates:
        if not isinstance(update, dict) or type(update.get("id")) is not int:
            raise InvalidPdfError
        identifier = update["id"]
        field = fields.get(identifier)
        if not field or identifier in seen or field["type"] == "unsupported":
            raise InvalidPdfError
        seen.add(identifier)
        value = update.get("value")
        if field["type"] == "checkbox":
            if type(value) is not bool:
                raise InvalidPdfError
        elif (
            not isinstance(value, str)
            or len(value) > 5000
            or (field["max_length"] and len(value) > field["max_length"])
        ):
            raise InvalidPdfError


def fill_form(document, updates: list[dict[str, Any]]) -> None:
    validate_form_updates(document, updates)
    changes = {update["id"]: update["value"] for update in updates}
    for page in document:
        for widget in page.widgets() or []:
            if widget.xref in changes:
                value = changes[widget.xref]
                widget.field_value = (
                    widget.on_state()
                    if widget.field_type == pymupdf.PDF_WIDGET_TYPE_CHECKBOX and value
                    else ("Off" if widget.field_type == pymupdf.PDF_WIDGET_TYPE_CHECKBOX else value)
                )
                widget.update()


def validate_edit_options(options: dict[str, Any], page_count: int) -> None:
    page = options.get("page")
    kind = options.get("kind")
    if type(page) is not int or not 1 <= page <= page_count:
        raise InvalidPdfError
    validate_crop_options({"rectangle": options.get("rectangle"), "ranges": str(page)}, page_count)
    if kind not in ("text", "image", "shape", "note"):
        raise InvalidPdfError
    color = options.get("color")
    if not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        raise InvalidPdfError
    if kind in ("text", "note"):
        value = options.get("text")
        if not isinstance(value, str) or not value.strip() or len(value) > 500:
            raise InvalidPdfError
    if kind == "text":
        size = options.get("font_size")
        if (
            type(size) is not int
            or not 8 <= size <= 72
            or options.get("font") not in ("helv", "tiro", "cour")
        ):
            raise InvalidPdfError
        font = pymupdf.Font(fontfile=str(FONT_DIR / EDIT_FONTS[options["font"]]))
        if any(char not in "\n\r\t" and not font.has_glyph(ord(char)) for char in value):
            raise InvalidPdfError
    if kind == "note" and any(ord(char) > 255 for char in value):
        raise InvalidPdfError
    if kind == "shape" and options.get("shape") not in ("rectangle", "ellipse"):
        raise InvalidPdfError


def edit_page(page: pymupdf.Page, options: dict[str, Any], image_path: Path | None) -> None:
    x0, y0, x1, y1 = options["rectangle"]
    rect = (
        pymupdf.Rect(
            x0 * page.rect.width, y0 * page.rect.height, x1 * page.rect.width, y1 * page.rect.height
        )
        * page.derotation_matrix
    )
    color = _rgb_color(options["color"])
    kind = options["kind"]
    if kind == "text":
        if (
            page.insert_textbox(
                rect,
                options["text"],
                fontsize=options["font_size"],
                fontname="OpenConverterFont",
                fontfile=str(FONT_DIR / EDIT_FONTS[options["font"]]),
                color=color,
                rotate=page.rotation,
            )
            < 0
        ):
            raise InvalidPdfError("Text does not fit in the selected area")
    elif kind == "image":
        if image_path is None:
            raise InvalidPdfError
        with Image.open(image_path) as source_image:
            prepared = ImageOps.exif_transpose(source_image).convert("RGBA")
            output = BytesIO()
            prepared.save(output, format="PNG")
        page.insert_image(
            rect, stream=output.getvalue(), keep_proportion=True, rotate=page.rotation
        )
    elif kind == "shape":
        if options["shape"] == "ellipse":
            page.draw_oval(rect, color=color, width=2)
        else:
            page.draw_rect(rect, color=color, width=2)
    else:
        annotation = page.add_freetext_annot(rect, options["text"], text_color=color, fontsize=12)
        annotation.update()


def inspect_pdf(path: Path) -> int:
    try:
        with pymupdf.open(path) as document:
            if (
                not document.is_pdf
                or document.needs_pass
                or document.is_repaired
                or document.page_count < 1
            ):
                raise InvalidPdfError
            return document.page_count
    except InvalidPdfError:
        raise
    except Exception as exc:
        raise InvalidPdfError from exc


def inspect_protected_pdf(path: Path, password: str) -> int:
    try:
        with pymupdf.open(path) as document:
            if (
                not document.is_pdf
                or document.xref_get_key(-1, "Encrypt")[0] == "null"
                or not document.authenticate(password)
                or document.is_repaired
                or document.page_count < 1
            ):
                raise InvalidPdfError
            return document.page_count
    except InvalidPdfError:
        raise
    except Exception as exc:
        raise InvalidPdfError from exc


def _open_pdf(path: Path):
    document = pymupdf.open(path)
    if (
        not document.is_pdf
        or document.needs_pass
        or document.is_repaired
        or document.page_count < 1
    ):
        document.close()
        raise InvalidPdfError
    return document


def validate_page_ranges(value: str, page_count: int) -> list[tuple[int, int]]:
    if not value.strip():
        raise InvalidPdfError
    ranges: list[tuple[int, int]] = []
    used: set[int] = set()
    for part in value.split(","):
        match = re.fullmatch(r"\s*(\d+)(?:\s*-\s*(\d+))?\s*", part)
        if not match:
            raise InvalidPdfError
        first = int(match.group(1))
        last = int(match.group(2) or first)
        if first < 1 or last < first or last > page_count:
            raise InvalidPdfError
        pages = set(range(first, last + 1))
        if used.intersection(pages):
            raise InvalidPdfError
        used.update(pages)
        ranges.append((first - 1, last - 1))
    return ranges


def _rgb_color(value: str) -> tuple[float, float, float]:
    normalized = value.lstrip("#")
    return tuple(int(normalized[index : index + 2], 16) / 255 for index in (0, 2, 4))  # type: ignore[return-value]


def _anchor_rect(
    page: pymupdf.Page,
    position: str,
    width: float,
    height: float,
    margin: float,
) -> tuple[pymupdf.Rect, int]:
    rect = page.rect
    horizontal, vertical = {
        "top_left": ("left", "top"),
        "top_center": ("center", "top"),
        "top_right": ("right", "top"),
        "center_left": ("left", "center"),
        "center": ("center", "center"),
        "center_right": ("right", "center"),
        "bottom_left": ("left", "bottom"),
        "bottom_center": ("center", "bottom"),
        "bottom_right": ("right", "bottom"),
    }[position]
    x0 = (
        rect.x0 + margin
        if horizontal == "left"
        else rect.x1 - margin - width
        if horizontal == "right"
        else rect.x0 + (rect.width - width) / 2
    )
    y0 = (
        rect.y0 + margin
        if vertical == "top"
        else rect.y1 - margin - height
        if vertical == "bottom"
        else rect.y0 + (rect.height - height) / 2
    )
    return pymupdf.Rect(x0, y0, x0 + width, y0 + height), {"left": 0, "center": 1, "right": 2}[
        horizontal
    ]


def _apply_text_watermark(document, options: dict[str, Any]) -> None:
    color = _rgb_color(str(options["color"]))
    font_size = int(options["font_size"])
    for page in document:
        box_width = page.rect.width * 0.9
        box_height = page.rect.height * 0.7
        box, alignment = _anchor_rect(
            page, str(options["position"]), box_width, box_height, margin=24
        )
        written = page.insert_textbox(
            box,
            str(options["text"]),
            fontname=str(options["font"]),
            fontsize=font_size,
            color=color,
            fill_opacity=float(options["opacity"]),
            align=alignment,
            overlay=True,
        )
        if written < 0:
            raise InvalidPdfError("Watermark text does not fit on the page")


def _prepare_watermark_image(
    source: Path, destination: Path, max_size: tuple[int, int], opacity: float
) -> tuple[int, int]:
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGBA")
        image.thumbnail(max_size, Image.Resampling.LANCZOS)
        alpha = image.getchannel("A").point(lambda value: round(value * opacity))
        image.putalpha(alpha)
        image.save(destination, format="PNG", optimize=True)
        return image.size


def _apply_image_watermark(
    document,
    image_source: Path,
    output_dir: Path,
    options: dict[str, Any],
) -> None:
    first_page = document[0]
    max_size = (
        max(1, round(first_page.rect.width * 0.24)),
        max(1, round(first_page.rect.height * 0.2)),
    )
    image_path = output_dir / "watermark.png"
    image_size = _prepare_watermark_image(
        image_source, image_path, max_size, float(options["opacity"])
    )
    for page in document:
        box, _ = _anchor_rect(page, str(options["position"]), *image_size, margin=24)
        page.insert_image(box, filename=str(image_path), keep_proportion=True, overlay=True)


def _page_number_text(number: int, total: int, format_name: str, language: str) -> str:
    if format_name == "number":
        return str(number)
    if format_name == "number_total":
        return f"{number} / {total}"
    label = "Página" if language == "pt-BR" else "Page"
    connector = "de" if language == "pt-BR" else "of"
    return f"{label} {number} {connector} {total}"


def _apply_page_numbers(document, options: dict[str, Any]) -> None:
    position = str(options["position"])
    horizontal = position.rsplit("_", 1)[1]
    alignment = {"left": 0, "center": 1, "right": 2}[horizontal]
    font_size = int(options["font_size"])
    color = _rgb_color(str(options["color"]))
    total = document.page_count
    start = int(options["start"])
    for index, page in enumerate(document):
        text = _page_number_text(
            index + start, total, str(options["format"]), str(options["language"])
        )
        box, _ = _anchor_rect(page, position, page.rect.width * 0.9, font_size * 1.8, margin=18)
        page.insert_textbox(
            box,
            text,
            fontname=str(options["font"]),
            fontsize=font_size,
            color=color,
            align=alignment,
            overlay=True,
        )


def process_pdf(
    operation: str,
    sources: list[tuple[Path, str]],
    options: dict[str, Any],
    output_dir: Path,
    secret: str | None = None,
) -> tuple[list[Path], str]:
    """Run one PDF operation; returned paths are ready-to-download artifacts."""
    output_dir.mkdir(parents=True, exist_ok=True)
    if operation == "pdf.pdfa":
        if len(sources) != 1:
            raise InvalidPdfError
        destination = output_dir / "archival.pdf"
        convert_pdfa(sources[0][0], destination)
        return [destination], "application/pdf"
    if operation == "pdf.compare":
        return [compare_pdfs(sources, output_dir, options["language"])], "text/html; charset=utf-8"
    if operation == "pdf.repair":
        if len(sources) != 1:
            raise InvalidPdfError
        try:
            with pymupdf.open(sources[0][0]) as document:
                if not document.is_pdf or document.needs_pass or document.page_count < 1:
                    raise InvalidPdfError
                destination = output_dir / "repaired.pdf"
                document.save(destination, garbage=4, deflate=True)
            inspect_pdf(destination)
        except InvalidPdfError:
            raise
        except Exception as exc:
            raise InvalidPdfError from exc
        return [destination], "application/pdf"
    if operation in {"pdf.protect", "pdf.unlock"}:
        if len(sources) != 1 or not secret:
            raise InvalidPdfError
        if operation == "pdf.unlock":
            inspect_protected_pdf(sources[0][0], secret)
            document = pymupdf.open(sources[0][0])
            document.authenticate(secret)
        else:
            document = _open_pdf(sources[0][0])
        try:
            destination = output_dir / (
                "protected.pdf" if operation == "pdf.protect" else "unlocked.pdf"
            )
            if operation == "pdf.protect":
                document.save(
                    destination,
                    encryption=pymupdf.PDF_ENCRYPT_AES_256,
                    owner_pw=secret,
                    user_pw=secret,
                    garbage=3,
                    deflate=True,
                )
            else:
                document.save(
                    destination, encryption=pymupdf.PDF_ENCRYPT_NONE, garbage=3, deflate=True
                )
        finally:
            document.close()
        return [destination], "application/pdf"
    if operation in {"pdf.edit", "pdf.sign"}:
        document = _open_pdf(sources[0][0])
        try:
            validate_edit_options(options, document.page_count)
            edit_page(
                document[options["page"] - 1], options, sources[1][0] if len(sources) > 1 else None
            )
            destination = output_dir / "edited.pdf"
            document.save(destination, garbage=3, deflate=True, use_objstms=True)
        finally:
            document.close()
        return [destination], "application/pdf"
    if operation == "pdf.organize":
        documents = []
        output = pymupdf.open()
        try:
            for source, _ in sources:
                documents.append(_open_pdf(source))
            for file_number, page_number in options["pages"]:
                output.insert_pdf(
                    documents[file_number - 1], from_page=page_number - 1, to_page=page_number - 1
                )
            destination = output_dir / "organized.pdf"
            output.save(destination, garbage=3, deflate=True, use_objstms=True)
        finally:
            output.close()
            for document in documents:
                document.close()
        return [destination], "application/pdf"
    if operation == "pdf.merge":
        merged = pymupdf.open()
        try:
            for source, _ in sources:
                document = _open_pdf(source)
                try:
                    merged.insert_pdf(document)
                finally:
                    document.close()
            destination = output_dir / "merged.pdf"
            merged.save(destination, garbage=3, deflate=True, use_objstms=True)
        finally:
            merged.close()
        return [destination], "application/pdf"

    if operation == "image.to_pdf":
        output = pymupdf.open()
        try:
            for source, _ in sources:
                image = pymupdf.open(source)
                try:
                    width, height = image[0].rect.width, image[0].rect.height
                finally:
                    image.close()
                landscape = width > height
                page_width, page_height = (842.0, 595.0) if landscape else (595.0, 842.0)
                page = output.new_page(width=page_width, height=page_height)
                margin = 28.35
                page.insert_image(
                    pymupdf.Rect(margin, margin, page_width - margin, page_height - margin),
                    filename=str(source),
                    keep_proportion=True,
                )
            destination = output_dir / "images.pdf"
            output.save(destination, garbage=3, deflate=True, use_objstms=True)
        finally:
            output.close()
        return [destination], "application/pdf"

    if operation == "pdf.watermark":
        pdf_sources = [(path, name) for path, name in sources if path.suffix.lower() == ".pdf"]
        image_sources = [(path, name) for path, name in sources if path.suffix.lower() != ".pdf"]
        if len(pdf_sources) != 1 or (options["kind"] == "image" and len(image_sources) != 1):
            raise InvalidPdfError
        if options["kind"] == "text" and image_sources:
            raise InvalidPdfError
        source, _ = pdf_sources[0]
        document = _open_pdf(source)
        try:
            if options["kind"] == "text":
                _apply_text_watermark(document, options)
            else:
                _apply_image_watermark(document, image_sources[0][0], output_dir, options)
            destination = output_dir / "watermarked.pdf"
            document.save(destination, garbage=3, deflate=True, use_objstms=True)
        finally:
            document.close()
        return [destination], "application/pdf"

    if operation == "pdf.page_numbers":
        if len(sources) != 1:
            raise InvalidPdfError
        source, _ = sources[0]
        document = _open_pdf(source)
        try:
            _apply_page_numbers(document, options)
            destination = output_dir / "numbered.pdf"
            document.save(destination, garbage=3, deflate=True, use_objstms=True)
        finally:
            document.close()
        return [destination], "application/pdf"

    if len(sources) != 1:
        raise InvalidPdfError
    source, original_name = sources[0]
    if operation in {"pdf.to_word", "pdf.to_powerpoint", "pdf.to_excel"}:
        if not word_isolated():
            unavailable_errors = {
                "pdf.to_word": WordUnavailableError,
                "pdf.to_powerpoint": PowerPointUnavailableError,
                "pdf.to_excel": ExcelUnavailableError,
            }
            raise unavailable_errors[operation]
    document = _open_pdf(source)
    try:
        if operation == "pdf.to_word":
            destination = output_dir / "converted.docx"
            try:
                completed = subprocess.run(
                    [sys.executable, "-m", "i_love_open_converter.word_worker",
                     str(source.resolve()), str(destination.resolve())],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=180, check=False,
                )
                if completed.returncode != 0 or not destination.is_file():
                    raise WordConversionError
                with zipfile.ZipFile(destination) as archive:
                    if not {"[Content_Types].xml", "word/document.xml"} <= set(archive.namelist()):
                        raise WordConversionError
                    if archive.getinfo("word/document.xml").file_size > 64 * 1024 * 1024:
                        raise WordConversionError
                    ElementTree.fromstring(archive.read("word/document.xml"))
            except (OSError, subprocess.TimeoutExpired, zipfile.BadZipFile,
                    ElementTree.ParseError) as exc:
                raise WordConversionError from exc
            content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            return [destination], content_type

        if operation == "pdf.to_powerpoint":
            destination = output_dir / "presentation.pptx"
            try:
                completed = subprocess.run(
                    [sys.executable, "-m", "i_love_open_converter.powerpoint_worker",
                     str(source.resolve()), str(destination.resolve())],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=180, check=False,
                )
                if completed.returncode != 0 or not destination.is_file():
                    raise PowerPointConversionError
                if destination.stat().st_size > 256 * 1024**2:
                    raise PowerPointConversionError
                with zipfile.ZipFile(destination) as archive:
                    names = set(archive.namelist())
                    slide_names = {name for name in names
                                   if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)}
                    if not {"[Content_Types].xml", "ppt/presentation.xml",
                            "ppt/slides/slide1.xml"} <= names:
                        raise PowerPointConversionError
                    if len(slide_names) != document.page_count or len(names) > 10_000:
                        raise PowerPointConversionError
                    if sum(item.file_size for item in archive.infolist()) > 512 * 1024**2:
                        raise PowerPointConversionError
                    for name in ("ppt/presentation.xml", "ppt/slides/slide1.xml"):
                        if archive.getinfo(name).file_size > 64 * 1024**2:
                            raise PowerPointConversionError
                        ElementTree.fromstring(archive.read(name))
            except (OSError, subprocess.TimeoutExpired, zipfile.BadZipFile,
                    ElementTree.ParseError, RuntimeError) as exc:
                raise PowerPointConversionError from exc
            content_type = (
                "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            )
            return [destination], content_type

        if operation == "pdf.to_excel":
            destination = output_dir / "extracted-data.xlsx"
            try:
                completed = subprocess.run(
                    [sys.executable, "-m", "i_love_open_converter.excel_worker",
                     str(source.resolve()), str(destination.resolve())],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=180, check=False,
                )
                if completed.returncode == 3:
                    raise NoSpreadsheetDataError
                if completed.returncode != 0 or not destination.is_file():
                    raise ExcelConversionError
                if destination.stat().st_size > 256 * 1024**2:
                    raise ExcelConversionError
                with zipfile.ZipFile(destination) as archive:
                    names = set(archive.namelist())
                    worksheet_names = {
                        name for name in names
                        if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name)
                    }
                    if not {"[Content_Types].xml", "xl/workbook.xml"} <= names:
                        raise ExcelConversionError
                    if not worksheet_names or len(worksheet_names) > 2 or len(names) > 1000:
                        raise ExcelConversionError
                    if sum(item.file_size for item in archive.infolist()) > 512 * 1024**2:
                        raise ExcelConversionError
                    for name in names:
                        if name.endswith(".xml"):
                            if archive.getinfo(name).file_size > 64 * 1024**2:
                                raise ExcelConversionError
                            ElementTree.fromstring(archive.read(name))
            except (OSError, subprocess.TimeoutExpired, zipfile.BadZipFile,
                    ElementTree.ParseError, RuntimeError) as exc:
                raise ExcelConversionError from exc
            content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            return [destination], content_type

        if operation == "pdf.to_markdown":
            try:
                completed = subprocess.run(
                    [sys.executable, "-m", "i_love_open_converter.markdown_worker",
                     str(source.resolve()), str(output_dir.resolve())],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=180, check=False,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise MarkdownConversionError from exc
            destination = output_dir / "document.md"
            if completed.returncode != 0 or not destination.is_file():
                raise MarkdownConversionError
            assets = sorted(output_dir.glob("image-*.png"))
            return [destination, *assets], "text/markdown"

        if operation == "pdf.ocr":
            destination = output_dir / "searchable.pdf"
            make_searchable_pdf(source, destination, options["language"])
            return [destination], "application/pdf"

        if operation == "pdf.extract_images":
            seen: set[int] = set()
            paths: list[Path] = []
            ordered = image_order(source)
            if len(ordered) != document.page_count:
                raise InvalidPdfError
            for page, references in zip(document, ordered, strict=True):
                blocks = [block for block in page.get_text("dict")["blocks"] if block["type"] == 1]
                if len(references) != len(blocks):
                    raise InvalidPdfError
                for xref, block in zip(references, blocks, strict=True):
                    if xref and xref in seen:
                        continue
                    if xref:
                        seen.add(xref)
                    base = pymupdf.Pixmap(block["image"])
                    mask = block.get("mask")
                    if mask:
                        base = pymupdf.Pixmap(base, pymupdf.Pixmap(mask))
                    if base.colorspace is None:
                        continue
                    if base.colorspace.n not in (1, 3):
                        base = pymupdf.Pixmap(pymupdf.csRGB, base)
                    destination = output_dir / f"image-{len(paths) + 1:03d}.png"
                    base.save(destination)
                    paths.append(destination)
            if not paths:
                raise NoEmbeddedImagesError
            return paths, "image/png"

        if operation == "pdf.forms":
            fill_form(document, options["updates"])
            destination = output_dir / "filled.pdf"
            document.save(destination, garbage=3, deflate=True)
            return [destination], "application/pdf"
        if operation == "pdf.redact":
            redact_pages(document, options)
            destination = output_dir / "redacted.pdf"
            document.save(destination, garbage=4, deflate=True)
            return [destination], "application/pdf"

        if operation == "pdf.crop":
            for page_number in validate_crop_options(options, document.page_count):
                crop_page(document[page_number], options["rectangle"])
            destination = output_dir / "cropped.pdf"
            document.save(destination, garbage=3, deflate=True, use_objstms=True)
            return [destination], "application/pdf"

        if operation == "pdf.rotate":
            degrees = int(options["degrees"])
            for page in document:
                page.set_rotation((page.rotation + degrees) % 360)
            destination = output_dir / "rotated.pdf"
            document.save(destination, garbage=3, deflate=True, use_objstms=True)
            return [destination], "application/pdf"

        if operation == "pdf.compress":
            destination = output_dir / "compressed.pdf"
            document.save(destination, garbage=3, deflate=True, use_objstms=True)
            return [destination], "application/pdf"

        if operation == "pdf.split":
            outputs: list[Path] = []
            for index, (first, last) in enumerate(
                validate_page_ranges(str(options.get("ranges", "")), document.page_count), start=1
            ):
                piece = pymupdf.open()
                try:
                    piece.insert_pdf(document, from_page=first, to_page=last)
                    destination = output_dir / f"{Path(original_name).stem}-part-{index}.pdf"
                    piece.save(destination, garbage=3, deflate=True, use_objstms=True)
                    outputs.append(destination)
                finally:
                    piece.close()
            return outputs, "application/pdf"

        if operation == "pdf.to_image":
            from PIL import Image

            outputs = []
            stem = Path(original_name).stem
            for index, page in enumerate(document, start=1):
                pixmap = page.get_pixmap(dpi=150, colorspace=pymupdf.csRGB, alpha=False)
                destination = output_dir / f"{stem}-page-{index}.jpg"
                image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
                image.save(destination, format="JPEG", quality=85, optimize=True)
                outputs.append(destination)
            return outputs, "image/jpeg"

    except (InvalidPdfError, NoOcrTextError, OcrProcessingError, MarkdownConversionError,
            NoEmbeddedImagesError, WordConversionError, PowerPointConversionError,
            ExcelConversionError):
        raise
    except Exception as exc:
        raise InvalidPdfError from exc
    finally:
        document.close()
    raise InvalidPdfError
