from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps, UnidentifiedImageError

INPUT_FORMATS = {"JPEG", "PNG", "WEBP", "BMP", "TIFF"}
OUTPUT_FORMATS = {"JPEG", "PNG", "WEBP"}
Image.MAX_IMAGE_PIXELS = 100_000_000
warnings.simplefilter("error", Image.DecompressionBombWarning)


class InvalidImageError(Exception):
    pass


class UnsupportedImageError(Exception):
    pass


class InvalidImageOptionsError(Exception):
    pass


def validate_image_crop_options(options: dict[str, Any]) -> dict[str, int]:
    values: dict[str, int] = {}
    for name in ("left", "top", "width", "height"):
        raw = options.get(name)
        minimum = 0 if name in {"left", "top"} else 1
        maximum = 9_999 if name in {"left", "top"} else 10_000
        if isinstance(raw, bool) or not str(raw).isdigit() or not minimum <= int(raw) <= maximum:
            raise InvalidImageOptionsError
        values[name] = int(raw)
    return values


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
        elif operation == "image.crop":
            crop = validate_image_crop_options(options)
            right, bottom = crop["left"] + crop["width"], crop["top"] + crop["height"]
            if right > image.width or bottom > image.height:
                raise InvalidImageOptionsError
            image = image.crop((crop["left"], crop["top"], right, bottom))
        elif operation == "image.rotate":
            degrees = int(options["degrees"])
            image = image.rotate(-degrees, expand=True)
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
