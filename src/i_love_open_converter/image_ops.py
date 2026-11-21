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


def _watermark_offset(
    canvas_size: tuple[int, int], mark_size: tuple[int, int], position: str
) -> tuple[int, int]:
    width, height = canvas_size
    mark_width, mark_height = mark_size
    inset = max(4, round(min(width, height) * 0.02))
    horizontal = position.rsplit("_", 1)[-1] if "_" in position else position
    vertical = position.split("_", 1)[0] if "_" in position else position
    x = (
        inset
        if horizontal == "left"
        else width - mark_width - inset
        if horizontal == "right"
        else (width - mark_width) // 2
    )
    y = (
        inset
        if vertical == "top"
        else height - mark_height - inset
        if vertical == "bottom"
        else (height - mark_height) // 2
    )
    return max(0, x), max(0, y)


def _apply_image_watermark(
    image: Image.Image, options: dict[str, Any], watermark_path: Path | None
) -> Image.Image:
    base = image.convert("RGBA")
    opacity = int(options["opacity"])
    position = str(options["position"])
    if options["kind"] == "text":
        text = str(options["text"])
        inset = max(4, round(min(base.size) * 0.02))
        available_width = max(1, base.width - 2 * inset)
        font_size = max(12, round(min(base.size) * 0.05))
        font = ImageFont.load_default(size=font_size)
        measure = ImageDraw.Draw(base)
        bounds = measure.textbbox((0, 0), text, font=font, stroke_width=2)
        if bounds[2] - bounds[0] > available_width:
            font_size = max(1, round(font_size * available_width / (bounds[2] - bounds[0])))
            font = ImageFont.load_default(size=font_size)
            bounds = measure.textbbox((0, 0), text, font=font, stroke_width=2)
        mark_size = (bounds[2] - bounds[0], bounds[3] - bounds[1])
        x, y = _watermark_offset(base.size, mark_size, position)
        mark = Image.new("RGBA", base.size, (0, 0, 0, 0))
        ImageDraw.Draw(mark).text(
            (x - bounds[0], y - bounds[1]),
            text,
            font=font,
            fill=(255, 255, 255, round(255 * opacity / 100)),
            stroke_width=2,
            stroke_fill=(0, 0, 0, round(255 * opacity / 100)),
        )
        base.alpha_composite(mark)
        mark.close()
        return base

    if watermark_path is None:
        base.close()
        raise UnsupportedImageError
    with Image.open(watermark_path) as opened_mark:
        if (opened_mark.format or "").upper() not in {"PNG", "JPEG", "WEBP"}:
            base.close()
            raise UnsupportedImageError
        mark = ImageOps.exif_transpose(opened_mark).convert("RGBA")
    try:
        max_side = max(1, int(min(base.size) * 0.25))
        scale = min(1.0, max_side / max(mark.size))
        if scale < 1.0:
            resized = mark.resize(
                (max(1, round(mark.width * scale)), max(1, round(mark.height * scale))),
                Image.Resampling.LANCZOS,
            )
            mark.close()
            mark = resized
        alpha = mark.getchannel("A")
        adjusted_alpha = alpha.point(lambda value: round(value * opacity / 100))
        alpha.close()
        mark.putalpha(adjusted_alpha)
        adjusted_alpha.close()
        x, y = _watermark_offset(base.size, mark.size, position)
        base.alpha_composite(mark, (x, y))
        return base
    except Exception:
        base.close()
        raise
    finally:
        mark.close()


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
    watermark_path: Path | None = None,
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
        elif operation == "image.watermark":
            image = _apply_image_watermark(image, options, watermark_path)
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


def convert_image(source: Path, destination: Path, output_format: str) -> tuple[str, int]:
    """Compatibility helper for simple format conversion."""
    return process_image(source, destination, "image.convert", {"format": output_format})
