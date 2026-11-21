from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError

INPUT_FORMATS = {"JPEG", "PNG", "WEBP", "BMP", "TIFF"}
OUTPUT_FORMATS = {"JPEG", "PNG", "WEBP"}
Image.MAX_IMAGE_PIXELS = 100_000_000
warnings.simplefilter("error", Image.DecompressionBombWarning)


class InvalidImageError(Exception):
    pass


class UnsupportedImageError(Exception):
    pass


def inspect_image(path: Path) -> tuple[str, str]:
    try:
        with Image.open(path) as image:
            image_format = (image.format or "").upper()
            if image_format not in INPUT_FORMATS:
                raise UnsupportedImageError
            if getattr(image, "n_frames", 1) != 1:
                raise UnsupportedImageError
            image.verify()
            return image_format, image.get_format_mimetype() or "application/octet-stream"
    except UnsupportedImageError:
        raise
    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise InvalidImageError from exc


def process_image(
    source: Path,
    destination: Path,
    operation: str,
    options: dict[str, Any],
) -> tuple[str, int]:
    output_format = str(options.get("format", "PNG")).upper()
    output_format = output_format.upper()
    if output_format == "JPG":
        output_format = "JPEG"
    if output_format not in OUTPUT_FORMATS:
        raise UnsupportedImageError

    with Image.open(source) as opened:
        if (opened.format or "").upper() not in INPUT_FORMATS:
            raise UnsupportedImageError
        if getattr(opened, "n_frames", 1) != 1:
            raise UnsupportedImageError
        image = ImageOps.exif_transpose(opened)
        icc_profile = image.info.get("icc_profile")
        if operation == "image.resize":
            width = options.get("width")
            height = options.get("height")
            image = ImageOps.contain(
                image,
                (width or image.width, height or image.height),
                method=Image.Resampling.LANCZOS,
            )
        elif operation == "image.rotate":
            degrees = int(options["degrees"])
            image = image.rotate(-degrees, expand=True)
        elif operation == "image.meme":
            image = image.convert("RGBA")
            _draw_meme_captions(image, options)
        if output_format == "JPEG":
            if image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info):
                rgba = image.convert("RGBA")
                background = Image.new("RGB", rgba.size, "white")
                background.paste(rgba, mask=rgba.getchannel("A"))
                image = background
            else:
                image = image.convert("RGB")
            image.save(
                destination,
                format="JPEG",
                quality=int(options.get("quality", 85)),
                optimize=True,
                icc_profile=icc_profile,
            )
            content_type = "image/jpeg"
        elif output_format == "PNG":
            image.save(destination, format="PNG", optimize=True, icc_profile=icc_profile)
            content_type = "image/png"
        else:
            image.save(
                destination,
                format="WEBP",
                quality=int(options.get("quality", 85)),
                method=4,
                icc_profile=icc_profile,
            )
            content_type = "image/webp"

    return content_type, destination.stat().st_size


def _draw_meme_captions(image: Image.Image, options: dict[str, Any]) -> None:
    draw = ImageDraw.Draw(image)
    inset = min(4, round(min(image.size) * 0.025), max(0, min(image.size) // 8))
    max_width = max(1, image.width - inset * 2)
    base_font_size = max(1, min(96, image.width // 8, image.height // 5))
    captions = (
        (str(options.get("top_text", "")).strip(), "top"),
        (str(options.get("bottom_text", "")).strip(), "bottom"),
    )

    for caption, position in captions:
        if not caption:
            continue
        font_size = base_font_size
        chosen_font = ImageFont.load_default(size=font_size)
        lines = _wrap_caption(draw, caption, chosen_font, max_width)
        max_height = max(1, (image.height - inset * 2) // 2)
        line_height = max(1, font_size + max(1, font_size // 8))
        while font_size > 1 and (len(lines) * line_height) > max_height:
            font_size -= 1
            chosen_font = ImageFont.load_default(size=font_size)
            lines = _wrap_caption(draw, caption, chosen_font, max_width)
            line_height = max(1, font_size + max(1, font_size // 8))

        max_lines = max(1, max_height // line_height)
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            last = lines[-1]
            while last and draw.textlength(f"{last}…", font=chosen_font) > max_width:
                last = last[:-1]
            lines[-1] = f"{last}…" if last else "…"
        block_height = line_height * len(lines)
        y = inset if position == "top" else max(inset, image.height - inset - block_height)
        for line in lines:
            bounds = draw.textbbox(
                (0, 0), line, font=chosen_font, stroke_width=max(2, font_size // 14)
            )
            x = (image.width - (bounds[2] - bounds[0])) // 2 - bounds[0]
            draw.text(
                (x, y),
                line,
                font=chosen_font,
                fill="white",
                stroke_width=max(2, font_size // 14),
                stroke_fill="black",
            )
            y += line_height


def _wrap_caption(
    draw: ImageDraw.ImageDraw, caption: str, font: ImageFont.ImageFont, max_width: int
) -> list[str]:
    words = caption.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
            current = ""
        for character in word:
            candidate = current + character
            if current and draw.textlength(candidate, font=font) > max_width:
                lines.append(current)
                current = character
            else:
                current = candidate
    if current:
        lines.append(current)
    return lines


def convert_image(source: Path, destination: Path, output_format: str) -> tuple[str, int]:
    """Compatibility helper for simple format conversion."""
    return process_image(source, destination, "image.convert", {"format": output_format})
