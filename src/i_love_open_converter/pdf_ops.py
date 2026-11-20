from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pymupdf
from PIL import Image, ImageOps


class InvalidPdfError(Exception):
    """The input is not a readable, unencrypted PDF."""


def inspect_pdf(path: Path) -> int:
    try:
        with pymupdf.open(path) as document:
            if document.needs_pass or document.is_repaired or document.page_count < 1:
                raise InvalidPdfError
            return document.page_count
    except InvalidPdfError:
        raise
    except Exception as exc:
        raise InvalidPdfError from exc


def _open_pdf(path: Path):
    document = pymupdf.open(path)
    if document.needs_pass or document.is_repaired or document.page_count < 1:
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
) -> tuple[list[Path], str]:
    """Run one PDF operation; returned paths are ready-to-download artifacts."""
    output_dir.mkdir(parents=True, exist_ok=True)
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
    document = _open_pdf(source)
    try:
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

    except InvalidPdfError:
        raise
    except Exception as exc:
        raise InvalidPdfError from exc
    finally:
        document.close()
    raise InvalidPdfError
