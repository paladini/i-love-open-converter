from __future__ import annotations

import math
import warnings
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError

INPUT_FORMATS = {"JPEG", "PNG", "GIF", "WEBP", "BMP", "TIFF"}
OUTPUT_FORMATS = {"JPEG", "PNG", "WEBP", "GIF"}
Image.MAX_IMAGE_PIXELS = 100_000_000
MAX_GIF_ANIMATION_PIXELS = 25_000_000
warnings.simplefilter("error", Image.DecompressionBombWarning)
EDITOR_POSITIONS = {
    "top_left",
    "top_center",
    "top_right",
    "center_left",
    "center",
    "center_right",
    "bottom_left",
    "bottom_center",
    "bottom_right",
}
EDITOR_COLORS = {"black", "white", "red", "orange", "yellow", "green", "blue", "purple"}
EDITOR_FILTERS = {"original", "grayscale", "sepia", "invert"}
EDITOR_FRAMES = {"none", "solid", "double"}
EDITOR_SIZES = {"small", "medium", "large"}
EDITOR_STICKERS = {"none", "heart", "star", "sun", "check", "arrow", "speech"}
EDITOR_COLOR_VALUES = {
    "black": (25, 30, 40),
    "white": (255, 255, 255),
    "red": (220, 53, 69),
    "orange": (245, 130, 32),
    "yellow": (250, 204, 21),
    "green": (34, 160, 107),
    "blue": (59, 105, 225),
    "purple": (139, 92, 246),
}


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


def _editor_offset(
    canvas_size: tuple[int, int], element_size: tuple[int, int], position: str
) -> tuple[int, int]:
    width, height = canvas_size
    element_width, element_height = element_size
    inset = max(4, round(min(width, height) * 0.02))
    horizontal = position.rsplit("_", 1)[-1] if "_" in position else position
    vertical = position.split("_", 1)[0] if "_" in position else position
    x = (
        inset
        if horizontal == "left"
        else width - element_width - inset
        if horizontal == "right"
        else (width - element_width) // 2
    )
    y = (
        inset
        if vertical == "top"
        else height - element_height - inset
        if vertical == "bottom"
        else (height - element_height) // 2
    )
    return max(0, x), max(0, y)


def _watermark_offset(
    canvas_size: tuple[int, int], mark_size: tuple[int, int], position: str
) -> tuple[int, int]:
    return _editor_offset(canvas_size, mark_size, position)


def _editor_filter(image: Image.Image, filter_name: str) -> Image.Image:
    if filter_name == "original":
        return image.convert("RGBA")
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    rgb = rgba.convert("RGB")
    rgba.close()
    if filter_name == "grayscale":
        filtered = rgb.convert("L").convert("RGB")
    elif filter_name == "sepia":
        gray = rgb.convert("L")
        filtered = ImageOps.colorize(gray, black="#272019", white="#f4d7a1").convert("RGB")
        gray.close()
    else:
        filtered = ImageOps.invert(rgb)
    rgb.close()
    filtered.putalpha(alpha)
    alpha.close()
    return filtered


def _apply_editor_text(image: Image.Image, options: dict[str, Any]) -> None:
    text = str(options.get("text", ""))
    if not text:
        return
    size_factor = {"small": 0.03, "medium": 0.05, "large": 0.08}[options["text_size"]]
    opacity = int(options["opacity"])
    inset = max(4, round(min(image.size) * 0.02))
    font_size = max(12, round(min(image.size) * size_factor))
    font = ImageFont.load_default(size=font_size)
    draw = ImageDraw.Draw(image)
    bounds = draw.textbbox((0, 0), text, font=font)
    available_width = max(1, image.width - 2 * inset)
    text_width = bounds[2] - bounds[0]
    if text_width > available_width:
        font = ImageFont.load_default(size=max(1, round(font_size * available_width / text_width)))
        bounds = draw.textbbox((0, 0), text, font=font)
    text_size = (bounds[2] - bounds[0], bounds[3] - bounds[1])
    x, y = _editor_offset(image.size, text_size, options["text_position"])
    color = EDITOR_COLOR_VALUES[options["text_color"]]
    draw.text(
        (x - bounds[0], y - bounds[1]),
        text,
        font=font,
        fill=(*color, round(255 * opacity / 100)),
        stroke_width=max(1, font_size // 16),
        stroke_fill=(25, 30, 40, round(190 * opacity / 100)),
    )


def _apply_editor_frame(image: Image.Image, options: dict[str, Any]) -> None:
    frame = options["frame"]
    if frame == "none":
        return
    width = max(1, round(min(image.size) * int(options["frame_width"]) / 100))
    color = EDITOR_COLOR_VALUES[options["frame_color"]]
    draw = ImageDraw.Draw(image)
    if frame == "solid":
        draw.rectangle(
            (0, 0, image.width - 1, image.height - 1), outline=(*color, 255), width=width
        )
        return
    line_width = max(1, width // 3)
    for offset in (0, width - line_width):
        if offset * 2 < min(image.size):
            draw.rectangle(
                (offset, offset, image.width - offset - 1, image.height - offset - 1),
                outline=(*color, 255),
                width=line_width,
            )


def _sticker_points(kind: str, x: int, y: int, side: int) -> tuple[str, list[tuple[int, int]]]:
    half = side // 2
    if kind == "heart":
        points = [
            (half, side),
            (side * 0.04, side * 0.42),
            (side * 0.08, side * 0.20),
            (side * 0.25, side * 0.08),
            (half, side * 0.34),
            (side * 0.75, side * 0.08),
            (side * 0.92, side * 0.20),
            (side * 0.96, side * 0.42),
        ]
        return "polygon", [(x + round(px), y + round(py)) for px, py in points]
    if kind == "star":
        points = []
        for index in range(10):
            angle = -math.pi / 2 + index * math.pi / 5
            radius = side * (0.5 if index % 2 == 0 else 0.22)
            points.append(
                (
                    round(x + half + math.cos(angle) * radius),
                    round(y + half + math.sin(angle) * radius),
                )
            )
        return "polygon", points
    if kind == "arrow":
        return "polygon", [
            (x, y + side * 0.35),
            (x + side * 0.58, y + side * 0.35),
            (x + side * 0.58, y),
            (x + side, y + half),
            (x + side * 0.58, y + side),
            (x + side * 0.58, y + side * 0.65),
            (x, y + side * 0.65),
        ]
    return kind, [(x, y), (x + side, y + side)]


def _apply_editor_sticker(image: Image.Image, options: dict[str, Any]) -> None:
    kind = options["sticker"]
    if kind == "none":
        return
    factor = {"small": 0.08, "medium": 0.12, "large": 0.18}[options["sticker_size"]]
    side = min(max(12, round(min(image.size) * factor)), min(image.size))
    x, y = _editor_offset(image.size, (side, side), options["sticker_position"])
    draw = ImageDraw.Draw(image)
    shape, points = _sticker_points(kind, x, y, side)
    color = (*EDITOR_COLOR_VALUES[options["sticker_color"]], 255)
    if shape == "polygon":
        draw.polygon(points, fill=color)
    elif shape == "sun":
        draw.ellipse((*points[0], *points[1]), fill=color)
        center_x, center_y = x + side // 2, y + side // 2
        ray = max(2, side // 5)
        for index in range(8):
            angle = math.pi * index / 4
            start = (
                round(center_x + math.cos(angle) * side * 0.53),
                round(center_y + math.sin(angle) * side * 0.53),
            )
            end = (
                round(center_x + math.cos(angle) * (side * 0.53 + ray)),
                round(center_y + math.sin(angle) * (side * 0.53 + ray)),
            )
            draw.line((start, end), fill=color, width=max(1, side // 12))
    elif shape == "check":
        draw.line(
            (
                x + side * 0.10,
                y + side * 0.53,
                x + side * 0.40,
                y + side * 0.82,
                x + side * 0.92,
                y + side * 0.18,
            ),
            fill=color,
            width=max(2, side // 8),
            joint="curve",
        )
    else:
        draw.rounded_rectangle((*points[0], *points[1]), radius=max(2, side // 5), fill=color)
        if shape == "speech":
            draw.polygon(
                [
                    (x + side * 0.22, y + side * 0.82),
                    (x + side * 0.18, y + side),
                    (x + side * 0.48, y + side * 0.82),
                ],
                fill=color,
            )


def _apply_editor(image: Image.Image, options: dict[str, Any]) -> Image.Image:
    edited = _editor_filter(image, options["filter"])
    if edited.mode != "RGBA":
        rgba = edited.convert("RGBA")
        edited.close()
        edited = rgba
    _apply_editor_frame(edited, options)
    _apply_editor_sticker(edited, options)
    _apply_editor_text(edited, options)
    return edited
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
        elif operation == "image.crop":
            crop = validate_image_crop_options(options)
            right, bottom = crop["left"] + crop["width"], crop["top"] + crop["height"]
            if right > image.width or bottom > image.height:
                raise InvalidImageOptionsError
            image = image.crop((crop["left"], crop["top"], right, bottom))
        elif operation == "image.rotate":
            degrees = int(options["degrees"])
            image = image.rotate(-degrees, expand=True)
        elif operation == "image.editor":
            image = _apply_editor(image, options)
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
