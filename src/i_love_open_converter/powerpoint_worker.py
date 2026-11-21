"""Create a resource-bounded editable PowerPoint from a PDF."""

from __future__ import annotations

import io
import os
import platform
import sys
import warnings
from pathlib import Path

MAX_PAGES = 200
MAX_PAGE_PIXELS = 16_000_000
MAX_SHAPES = 20_000
MAX_OUTPUT_BYTES = 256 * 1024**2
MAX_IMAGE_PIXELS = 16_000_000
MAX_SLIDE_INCHES = 13.333333


def _limit_resources() -> None:
    if sys.platform != "linux":
        raise RuntimeError("Linux resource limits are required")
    import resource

    if platform.machine().lower() == "aarch64":
        resource.setrlimit(resource.RLIMIT_DATA, (1536 * 1024**2, 1536 * 1024**2))
    else:
        resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (180, 180))
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_OUTPUT_BYTES, MAX_OUTPUT_BYTES))


def _safe_font_name(value: str) -> str:
    name = value.split("+")[-1].strip()
    return name[:64] or "Arial"


def _add_text_line(slide, line: dict, transform) -> None:
    from pptx.dml.color import RGBColor
    from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE
    from pptx.util import Inches, Pt

    x0, y0, x1, y1 = line["bbox"]
    left, top, width, height = transform((x0, y0, x1, y1))
    if width <= 0 or height <= 0:
        return
    box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    frame = box.text_frame
    frame.clear()
    frame.word_wrap = False
    frame.auto_size = MSO_AUTO_SIZE.NONE
    frame.margin_left = frame.margin_right = frame.margin_top = frame.margin_bottom = 0
    frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    paragraph = frame.paragraphs[0]
    for span in line.get("spans", []):
        content = span.get("text", "")
        if not content:
            continue
        run = paragraph.add_run()
        run.text = content
        run.font.name = _safe_font_name(span.get("font", "Arial"))
        font_size_pt = span.get("size", 12) * transform.scale * 72
        run.font.size = Pt(max(1, min(200, font_size_pt)))
        flags = span.get("flags", 0)
        run.font.bold = bool(flags & 16)
        run.font.italic = bool(flags & 2)
        color = span.get("color", 0)
        run.font.color.rgb = RGBColor((color >> 16) & 255, (color >> 8) & 255, color & 255)


def _add_image(slide, block: dict, transform) -> None:
    from PIL import Image, ImageOps
    from pptx.util import Inches

    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
    warnings.simplefilter("error", Image.DecompressionBombWarning)
    try:
        with Image.open(io.BytesIO(block["image"])) as source:
            if source.width * source.height > MAX_IMAGE_PIXELS:
                raise ValueError("Image exceeds the pixel limit")
            image = ImageOps.exif_transpose(source)
            image.load()
            buffer = io.BytesIO()
            if "A" in image.getbands() and image.getchannel("A").getextrema()[0] < 255:
                image.convert("RGBA").save(buffer, format="PNG", optimize=True)
            else:
                image.convert("RGB").save(buffer, format="JPEG", quality=88, optimize=True)
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        raise ValueError("Unsupported or oversized embedded image") from exc
    left, top, width, height = transform(block["bbox"])
    if width > 0 and height > 0:
        slide.shapes.add_picture(io.BytesIO(buffer.getvalue()), Inches(left), Inches(top),
                                 Inches(width), Inches(height))


def main(source: Path, destination: Path) -> None:
    _limit_resources()
    os.environ["OMP_NUM_THREADS"] = "1"
    import pymupdf
    from pptx import Presentation
    from pptx.util import Inches

    presentation = Presentation()
    shapes = 0
    with pymupdf.open(source) as document:
        if document.is_encrypted or not 1 <= document.page_count <= MAX_PAGES:
            raise ValueError("Invalid or over-limit PDF")
        first = document[0].rect
        if first.width <= 0 or first.height <= 0:
            raise ValueError("Invalid first-page dimensions")
        slide_factor = MAX_SLIDE_INCHES / max(first.width, first.height)
        slide_width = first.width * slide_factor
        slide_height = first.height * slide_factor
        presentation.slide_width = Inches(slide_width)
        presentation.slide_height = Inches(slide_height)
        blank = presentation.slide_layouts[6]

        for page in document:
            rect = page.rect
            if rect.width <= 0 or rect.height <= 0:
                raise ValueError("Invalid page dimensions")
            pixel_width, pixel_height = rect.width * 150 / 72, rect.height * 150 / 72
            if pixel_width * pixel_height > MAX_PAGE_PIXELS:
                raise ValueError("Page exceeds the pixel limit")
            scale = min(slide_width / rect.width, slide_height / rect.height)
            offset_x = (slide_width - rect.width * scale) / 2
            offset_y = (slide_height - rect.height * scale) / 2

            def transform(box, *, _scale=scale, _x=offset_x, _y=offset_y,
                          _left=rect.x0, _top=rect.y0):
                x0, y0, x1, y1 = box
                return ((_x + (x0 - _left) * _scale, _y + (y0 - _top) * _scale,
                         (x1 - x0) * _scale, (y1 - y0) * _scale))

            transform.scale = scale
            slide = presentation.slides.add_slide(blank)
            for block in page.get_text("dict")["blocks"]:
                if block.get("type") == 0:
                    for line in block.get("lines", []):
                        _add_text_line(slide, line, transform)
                        shapes += 1
                elif block.get("type") == 1 and block.get("image"):
                    _add_image(slide, block, transform)
                    shapes += 1
                if shapes > MAX_SHAPES:
                    raise ValueError("Presentation exceeds the shape limit")

    destination.parent.mkdir(parents=True, exist_ok=True)
    presentation.save(destination)
    if destination.stat().st_size > MAX_OUTPUT_BYTES:
        destination.unlink(missing_ok=True)
        raise ValueError("Presentation exceeds the output limit")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
