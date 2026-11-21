from __future__ import annotations

import warnings
from pathlib import Path
from threading import Lock
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps, UnidentifiedImageError

INPUT_FORMATS = {"JPEG", "PNG", "WEBP", "BMP", "TIFF"}
OUTPUT_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_UPSCALE_PIXELS = 40_000_000
MAX_BACKGROUND_REMOVAL_PIXELS = 40_000_000
Image.MAX_IMAGE_PIXELS = 100_000_000
warnings.simplefilter("error", Image.DecompressionBombWarning)
_BACKGROUND_SESSION = None
_BACKGROUND_SESSION_LOCK = Lock()


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


def inspect_image_dimensions(path: Path) -> tuple[int, int]:
    try:
        with Image.open(path) as opened:
            if (opened.format or "").upper() not in INPUT_FORMATS or getattr(
                opened, "n_frames", 1
            ) != 1:
                raise UnsupportedImageError
            return ImageOps.exif_transpose(opened).size
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
        elif operation == "image.upscale":
            scale = int(options["scale"])
            target = (image.width * scale, image.height * scale)
            if scale not in {2, 4} or target[0] * target[1] > MAX_UPSCALE_PIXELS:
                raise InvalidImageError
            if image.mode in {"1", "P", "PA"}:
                image = image.convert("RGBA" if "transparency" in image.info else "RGB")
            elif image.mode not in {"L", "LA", "RGB", "RGBA"}:
                image = image.convert("RGB")
            image = image.resize(target, resample=Image.Resampling.LANCZOS)
            image = _apply_unsharp_mask(image)
        elif operation == "image.remove_background":
            if image.width * image.height > MAX_BACKGROUND_REMOVAL_PIXELS:
                raise InvalidImageError
            image = _remove_image_background(image)
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


def _remove_image_background(image: Image.Image) -> Image.Image:
    global _BACKGROUND_SESSION
    with _BACKGROUND_SESSION_LOCK:
        if _BACKGROUND_SESSION is None:
            from rembg import new_session

            _BACKGROUND_SESSION = new_session("u2netp")
    from rembg import remove

    result = remove(image.convert("RGB"), session=_BACKGROUND_SESSION, post_process_mask=True)
    if not isinstance(result, Image.Image) or result.size != image.size:
        raise InvalidImageError
    return result.convert("RGBA")


def _apply_unsharp_mask(image: Image.Image) -> Image.Image:
    unsharp = ImageFilter.UnsharpMask(radius=1.0, percent=100, threshold=3)
    if image.mode == "RGBA":
        alpha = image.getchannel("A")
        sharpened = image.convert("RGB").filter(unsharp).convert("RGBA")
        sharpened.putalpha(alpha)
        return sharpened
    if image.mode == "LA":
        gray, alpha = image.split()
        return Image.merge("LA", (gray.filter(unsharp), alpha))
    if image.mode == "P" and "transparency" in image.info:
        rgba = image.convert("RGBA")
        alpha = rgba.getchannel("A")
        sharpened = rgba.convert("RGB").filter(unsharp).convert("RGBA")
        sharpened.putalpha(alpha)
        return sharpened
    if image.mode == "P":
        image = image.convert("RGB")
    return image.filter(unsharp)


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
        max_height = max(1, (image.height - inset * 2) // 2)
        chosen_font, lines, line_height = _fit_meme_caption(
            draw, caption, max_width, max_height, base_font_size
        )
        block_height = line_height * len(lines)
        y = inset if position == "top" else max(inset, image.height - inset - block_height)
        for line in lines:
            stroke_width = max(2, chosen_font.size // 14)
            bounds = draw.textbbox((0, 0), line, font=chosen_font, stroke_width=stroke_width)
            text_width = bounds[2] - bounds[0]
            x = (image.width - text_width - 1) // 2 - bounds[0]
            draw.text(
                (x, y),
                line,
                font=chosen_font,
                fill="white",
                stroke_width=stroke_width,
                stroke_fill="black",
            )
            # Pillow's bundled Aileron font is regular. A one-pixel white overdraw
            # thickens the glyphs while preserving the dark stroke around them.
            draw.text((x + 1, y), line, font=chosen_font, fill="white")
            y += line_height


def _fit_meme_caption(
    draw: ImageDraw.ImageDraw,
    caption: str,
    max_width: int,
    max_height: int,
    base_font_size: int,
) -> tuple[ImageFont.ImageFont, list[str], int]:
    font_size = base_font_size
    font = ImageFont.load_default(size=font_size)
    lines = _wrap_caption(draw, caption, font, max_width)
    line_height = max(1, font_size + max(1, font_size // 8))
    while font_size > 1 and len(lines) * line_height > max_height:
        font_size -= 1
        font = ImageFont.load_default(size=font_size)
        lines = _wrap_caption(draw, caption, font, max_width)
        line_height = max(1, font_size + max(1, font_size // 8))

    max_lines = max(1, max_height // line_height)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while last and draw.textlength(f"{last}…", font=font) > max_width:
            last = last[:-1]
        lines[-1] = f"{last}…" if last else "…"
    return font, lines, line_height


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
