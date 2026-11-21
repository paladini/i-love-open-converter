from __future__ import annotations

import math
import warnings
from pathlib import Path
from threading import Lock
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps, UnidentifiedImageError

INPUT_FORMATS = {"JPEG", "PNG", "GIF", "WEBP", "BMP", "TIFF"}
OUTPUT_FORMATS = {"JPEG", "PNG", "WEBP", "GIF"}
MAX_UPSCALE_PIXELS = 40_000_000
MAX_BACKGROUND_REMOVAL_PIXELS = 40_000_000
MAX_FACE_BLUR_PIXELS = 40_000_000
Image.MAX_IMAGE_PIXELS = 100_000_000
MAX_GIF_ANIMATION_PIXELS = 25_000_000
warnings.simplefilter("error", Image.DecompressionBombWarning)
_BACKGROUND_SESSION = None
_BACKGROUND_SESSION_LOCK = Lock()
_FACE_CASCADES = None
_FACE_CASCADES_LOCK = Lock()
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


class NoFacesDetectedError(Exception):
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
        elif operation == "image.blur_faces":
            if image.width * image.height > MAX_FACE_BLUR_PIXELS:
                raise InvalidImageError
            image = _blur_detected_faces(image)
        elif operation == "image.meme":
            image = image.convert("RGBA")
            _draw_meme_captions(image, options)
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


def _face_cascades():
    global _FACE_CASCADES
    with _FACE_CASCADES_LOCK:
        if _FACE_CASCADES is None:
            import cv2

            data_dir = Path(cv2.data.haarcascades)
            frontal = cv2.CascadeClassifier(str(data_dir / "haarcascade_frontalface_default.xml"))
            profile = cv2.CascadeClassifier(str(data_dir / "haarcascade_profileface.xml"))
            if frontal.empty() or profile.empty():
                raise InvalidImageError
            _FACE_CASCADES = (cv2, frontal, profile)
    return _FACE_CASCADES


def _detect_face_regions(image: Image.Image) -> list[tuple[int, int, int, int]]:
    import numpy as np

    cv2, frontal, profile = _face_cascades()
    preview = ImageOps.contain(image.convert("RGB"), (1600, 1600), method=Image.Resampling.LANCZOS)
    gray = cv2.cvtColor(np.asarray(preview), cv2.COLOR_RGB2GRAY)
    gray = cv2.equalizeHist(gray)
    regions = []
    for x, y, width, height in frontal.detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=5, minSize=(24, 24)
    ):
        regions.append((int(x), int(y), int(width), int(height)))
    for x, y, width, height in profile.detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=5, minSize=(24, 24)
    ):
        regions.append((int(x), int(y), int(width), int(height)))
    for x, y, width, height in profile.detectMultiScale(
        cv2.flip(gray, 1), scaleFactor=1.1, minNeighbors=5, minSize=(24, 24)
    ):
        regions.append((int(preview.width - x - width), int(y), int(width), int(height)))
    scale_x = image.width / preview.width
    scale_y = image.height / preview.height
    mapped = [
        (
            max(0, round(x * scale_x)),
            max(0, round(y * scale_y)),
            min(image.width, round((x + width) * scale_x)),
            min(image.height, round((y + height) * scale_y)),
        )
        for x, y, width, height in regions
    ]
    return _deduplicate_face_regions(mapped)


def _deduplicate_face_regions(
    regions: list[tuple[int, int, int, int]],
) -> list[tuple[int, int, int, int]]:
    kept = []
    for candidate in sorted(
        regions, key=lambda rect: (rect[2] - rect[0]) * (rect[3] - rect[1]), reverse=True
    ):
        left, top, right, bottom = candidate
        area = max(0, right - left) * max(0, bottom - top)
        if not area:
            continue
        duplicate = False
        for other in kept:
            x_overlap = max(0, min(right, other[2]) - max(left, other[0]))
            y_overlap = max(0, min(bottom, other[3]) - max(top, other[1]))
            intersection = x_overlap * y_overlap
            other_area = (other[2] - other[0]) * (other[3] - other[1])
            if intersection / max(1, area + other_area - intersection) > 0.45:
                duplicate = True
                break
        if not duplicate:
            kept.append(candidate)
    return kept


def _blur_detected_faces(image: Image.Image) -> Image.Image:
    regions = _detect_face_regions(image)
    if not regions:
        raise NoFacesDetectedError
    result = image.convert("RGBA" if "A" in image.getbands() else "RGB")
    for left, top, right, bottom in regions:
        width = right - left
        height = bottom - top
        padding_x = round(width * 0.22)
        padding_y = round(height * 0.22)
        box = (
            max(0, left - padding_x),
            max(0, top - padding_y),
            min(result.width, right + padding_x),
            min(result.height, bottom + padding_y),
        )
        region = result.crop(box)
        radius = max(15, round(min(width, height) * 0.22))
        if region.mode == "RGBA":
            alpha = region.getchannel("A")
            blurred = region.convert("RGB").filter(ImageFilter.GaussianBlur(radius))
            blurred.putalpha(alpha)
        else:
            blurred = region.filter(ImageFilter.GaussianBlur(radius))
        result.paste(blurred, box[:2])
    return result


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
