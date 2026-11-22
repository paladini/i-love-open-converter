"""Validation and isolated raster conversion for static SVG images."""

from __future__ import annotations

import base64
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote

from .office_ops import office_isolated

MAX_SVG_BYTES = 10 * 1024 * 1024
MAX_SVG_PIXELS = 40_000_000
SVG_TIMEOUT_SECONDS = 120
SVG_RENDERER_OUTPUT_LIMIT = 256 * 1024 * 1024
DEFAULT_SVG_SIZE = (300, 150)
SVG_UNSAFE_ELEMENTS = {
    "animate",
    "animatemotion",
    "animatetransform",
    "discard",
    "foreignobject",
    "script",
    "set",
}
SVG_SIZE_UNITS = {
    "": 1.0,
    "px": 1.0,
    "pt": 96 / 72,
    "pc": 16.0,
    "mm": 96 / 25.4,
    "cm": 96 / 2.54,
    "in": 96.0,
}


class InvalidSvgError(Exception):
    """The input is not a supported static SVG image."""


class SvgUnavailableError(Exception):
    """The required isolated Linux SVG renderer is unavailable."""


class SvgConversionError(Exception):
    """The isolated SVG renderer failed or exceeded its bounds."""


def _local_name(name: str) -> str:
    return name.rsplit("}", 1)[-1].lower()


def _length(value: str | None) -> float | None:
    if not value:
        return None
    value = value.strip().lower()
    index = 0
    while index < len(value) and value[index] in "+-.0123456789e":
        index += 1
    if index == 0:
        return None
    try:
        amount = float(value[:index])
    except ValueError:
        return None
    unit = value[index:].strip()
    if unit == "%" or unit not in SVG_SIZE_UNITS or not math.isfinite(amount):
        return None
    result = amount * SVG_SIZE_UNITS[unit]
    return result if result > 0 else None


def _view_box(root: ET.Element) -> tuple[float, float] | None:
    value = root.attrib.get("viewBox") or root.attrib.get("viewbox")
    if not value:
        return None
    parts = value.replace(",", " ").split()
    if len(parts) != 4:
        return None
    try:
        min_x, min_y, width, height = (float(part) for part in parts)
    except ValueError:
        return None
    if (
        not all(math.isfinite(item) for item in (min_x, min_y, width, height))
        or width <= 0
        or height <= 0
    ):
        return None
    return width, height


def _validate_static_svg(content: bytes) -> tuple[bytes, int, int]:
    if not content or len(content) > MAX_SVG_BYTES:
        raise InvalidSvgError
    upper = content.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise InvalidSvgError
    try:
        root = ET.fromstring(content)
    except (ET.ParseError, ValueError) as exc:
        raise InvalidSvgError from exc
    if _local_name(root.tag) != "svg":
        raise InvalidSvgError

    for element in root.iter():
        if _local_name(element.tag) in SVG_UNSAFE_ELEMENTS:
            raise InvalidSvgError
        if _local_name(element.tag) == "style":
            style_text = unquote(element.text or "").lower()
            if "@import" in style_text:
                raise InvalidSvgError
            for reference in re.findall(r"url\((.*?)\)", style_text):
                target = reference.strip(" '\"\t\r\n")
                if not (target.startswith("#") or target.startswith("data:")):
                    raise InvalidSvgError
        for name, value in element.attrib.items():
            attribute = _local_name(name)
            lowered = value.strip().lower()
            if attribute.startswith("on"):
                raise InvalidSvgError
            if attribute == "href" and lowered and not (
                lowered.startswith("#") or lowered.startswith("data:")
            ):
                raise InvalidSvgError
            decoded = unquote(value).lower()
            if "url(" in decoded and any(
                marker in decoded for marker in ("http:", "https:", "file:", "//")
            ):
                raise InvalidSvgError

    view_box = _view_box(root)
    width = _length(root.attrib.get("width"))
    height = _length(root.attrib.get("height"))
    if view_box:
        width = width or view_box[0]
        height = height or view_box[1]
    width = width or DEFAULT_SVG_SIZE[0]
    height = height or DEFAULT_SVG_SIZE[1]
    scale = min(
        1.0,
        MAX_SVG_PIXELS / max(width, height),
        math.sqrt(MAX_SVG_PIXELS / width) / math.sqrt(height),
    )
    output_width = max(1, math.floor(width * scale))
    output_height = max(1, math.floor(height * scale))
    while output_width * output_height > MAX_SVG_PIXELS:
        if output_width / width >= output_height / height:
            output_width -= 1
        else:
            output_height -= 1
    return content, output_width, output_height


def inspect_svg(source: Path) -> tuple[int, int]:
    try:
        if source.stat().st_size > MAX_SVG_BYTES:
            raise InvalidSvgError
        content = source.read_bytes()
        _, width, height = _validate_static_svg(content)
    except OSError as exc:
        raise InvalidSvgError from exc
    return width, height


def convert_svg_to_image(
    source: Path, destination: Path, image_format: str, width: int, height: int
) -> tuple[str, int]:
    if image_format not in {"PNG", "JPEG", "WEBP"}:
        raise InvalidSvgError
    if not office_isolated():
        raise SvgUnavailableError
    if not 1 <= width <= MAX_SVG_PIXELS or not 1 <= height <= MAX_SVG_PIXELS:
        raise InvalidSvgError
    try:
        content, checked_width, checked_height = _validate_static_svg(source.read_bytes())
    except OSError as exc:
        raise InvalidSvgError from exc
    if (checked_width, checked_height) != (width, height):
        raise InvalidSvgError

    suffix = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}[image_format]
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix="svg-render-") as temporary:
            root = Path(temporary).resolve()
            (root / "cache").mkdir()
            encoded = base64.b64encode(content).decode("ascii")
            document = (
                '<!doctype html><html><head><meta charset="utf-8"><style>'
                f"@page{{size:{width}px {height}px;margin:0}}"
                f"html,body{{margin:0;padding:0;width:{width}px;height:{height}px;overflow:hidden}}"
                f"img{{display:block;width:{width}px;height:{height}px}}"
                '</style></head><body><img alt="" src="data:image/svg+xml;base64,'
                f'{encoded}"></body></html>'
            )
            html_path = root / "input.html"
            rendered_path = root / f"rendered{suffix}"
            html_path.write_text(document, encoding="utf-8")
            environment = {
                **os.environ,
                "HOME": str(root),
                "TMPDIR": str(root),
                "XDG_CACHE_HOME": str(root / "cache"),
                "PYTHONDONTWRITEBYTECODE": "1",
            }
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "i_love_open_converter.html_worker", str(root),
                     str(html_path), str(rendered_path), image_format.lower()],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=SVG_TIMEOUT_SECONDS,
                    check=False,
                    env=environment,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise SvgConversionError from exc
            if result.returncode == 77:
                raise SvgUnavailableError
            if result.returncode != 0 or not rendered_path.is_file():
                raise SvgConversionError
            size = rendered_path.stat().st_size
            if not 0 < size <= SVG_RENDERER_OUTPUT_LIMIT:
                raise SvgConversionError
            shutil.copyfile(rendered_path, destination)
    except (OSError, shutil.Error) as exc:
        raise SvgConversionError from exc
    mime = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}[image_format]
    return mime, destination.stat().st_size
