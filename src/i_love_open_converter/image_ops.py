from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps, UnidentifiedImageError

INPUT_FORMATS = {"JPEG", "PNG", "WEBP", "BMP", "TIFF"}
OUTPUT_FORMATS = {"JPEG", "PNG", "WEBP", "GIF"}
Image.MAX_IMAGE_PIXELS = 100_000_000
MAX_GIF_ANIMATION_PIXELS = 25_000_000
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
        opened_format = (opened.format or "").upper()
        if opened_format not in INPUT_FORMATS:
            raise UnsupportedImageError
        if operation == "image.from_jpg" and opened_format != "JPEG":
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
        elif output_format == "GIF":
            image.convert("RGB").save(destination, format="GIF", optimize=False)
            content_type = "image/gif"
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


def create_animated_gif(sources: list[Path], destination: Path) -> tuple[str, int]:
    if not sources:
        raise InvalidImageError
    canvas_width = 0
    canvas_height = 0
    try:
        for source in sources:
            with Image.open(source) as opened:
                if (opened.format or "").upper() != "JPEG" or getattr(opened, "n_frames", 1) != 1:
                    raise UnsupportedImageError
                width, height = opened.size
                if opened.getexif().get(274) in {5, 6, 7, 8}:
                    width, height = height, width
                canvas_width = max(canvas_width, width)
                canvas_height = max(canvas_height, height)
        canvas_size = (canvas_width, canvas_height)
        if canvas_width * canvas_height * len(sources) > MAX_GIF_ANIMATION_PIXELS:
            raise InvalidImageError
        frames: list[Image.Image] = []
        try:
            for source in sources:
                with Image.open(source) as opened:
                    image = ImageOps.exif_transpose(opened).convert("RGB")
                    try:
                        frame = Image.new("RGB", canvas_size, "white")
                        position = (
                            (canvas_width - image.width) // 2,
                            (canvas_height - image.height) // 2,
                        )
                        frame.paste(image, position)
                        frames.append(frame)
                    finally:
                        image.close()
            frames[0].save(
                destination,
                format="GIF",
                save_all=True,
                append_images=frames[1:],
                duration=500,
                loop=0,
                disposal=2,
                optimize=False,
            )
        finally:
            for frame in frames:
                frame.close()
        return "image/gif", destination.stat().st_size
    except (OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise InvalidImageError from exc


def convert_image(source: Path, destination: Path, output_format: str) -> tuple[str, int]:
    """Compatibility helper for simple format conversion."""
    return process_image(source, destination, "image.convert", {"format": output_format})
