from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pymupdf


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


def process_pdf(
    operation: str,
    sources: list[tuple[Path, str]],
    options: dict[str, Any],
    output_dir: Path,
) -> tuple[list[Path], str]:
    """Run one PDF operation; returned paths are ready-to-download artifacts."""
    output_dir.mkdir(parents=True, exist_ok=True)
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
