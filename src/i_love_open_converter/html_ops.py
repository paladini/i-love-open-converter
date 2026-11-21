"""Bounded, local-only HTML document rendering."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile, ZipFile

import pymupdf
from PIL import Image

from .office_ops import office_isolated

MAX_HTML_BYTES = 10 * 1024 * 1024
MAX_HTML_OUTPUT_BYTES = 256 * 1024 * 1024
MAX_HTML_IMAGE_OUTPUT_BYTES = MAX_HTML_OUTPUT_BYTES
MAX_HTML_PAGES = 100
HTML_TIMEOUT_SECONDS = 120
HTML_IMAGE_DPI = 144
MAX_HTML_PAGE_PIXELS = 40_000_000


class HtmlConversionError(Exception):
    """HTML rendering failed or exceeded its processing bounds."""


class HtmlUnavailableError(HtmlConversionError):
    """The required Linux, Landlock, or network isolation is unavailable."""


class HtmlExternalResourceError(HtmlConversionError):
    """The input references a resource other than an embedded data URI."""


def allowed_html_resource(url: str) -> bool:
    """Only embedded data resources are available to untrusted HTML and CSS."""
    return url[:5].lower() == "data:"


def convert_html(source: Path, output_dir: Path) -> Path:
    return _convert_html(source, output_dir, "pdf")


def convert_html_to_images(source: Path, output_dir: Path, image_format: str) -> Path:
    if image_format not in {"jpg", "svg"}:
        raise HtmlConversionError
    return _convert_html(source, output_dir, image_format)


def _convert_html(source: Path, output_dir: Path, output_format: str) -> Path:
    if not office_isolated():
        raise HtmlUnavailableError
    if source.suffix.lower() not in {".html", ".htm"}:
        raise HtmlConversionError
    try:
        if source.stat().st_size > MAX_HTML_BYTES:
            raise HtmlConversionError
    except OSError as exc:
        raise HtmlConversionError from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix="html-render-") as temporary:
            root = Path(temporary).resolve()
            local_source = root / "input" / f"document{source.suffix.lower()}"
            local_source.parent.mkdir()
            (root / "cache").mkdir()
            shutil.copyfile(source, local_source)
            rendered = root / ("rendered.pdf" if output_format == "pdf" else "rendered.zip")
            environment = {
                **os.environ,
                "HOME": str(root),
                "TMPDIR": str(root),
                "XDG_CACHE_HOME": str(root / "cache"),
                "PYTHONDONTWRITEBYTECODE": "1",
            }
            try:
                completed = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "i_love_open_converter.html_worker",
                        str(root),
                        str(local_source),
                        str(rendered),
                        output_format,
                    ],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=HTML_TIMEOUT_SECONDS,
                    check=False,
                    env=environment,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise HtmlConversionError from exc
            if completed.returncode == 77:
                raise HtmlUnavailableError
            if completed.returncode == 4:
                raise HtmlExternalResourceError
            if completed.returncode != 0 or not rendered.is_file():
                raise HtmlConversionError
            size = rendered.stat().st_size
            if size <= 0 or size > MAX_HTML_OUTPUT_BYTES:
                raise HtmlConversionError
            if output_format == "pdf":
                try:
                    with pymupdf.open(rendered) as document:
                        if (
                            not document.is_pdf
                            or document.needs_pass
                            or not 1 <= document.page_count <= MAX_HTML_PAGES
                        ):
                            raise HtmlConversionError
                except (RuntimeError, ValueError) as exc:
                    raise HtmlConversionError from exc
                destination = output_dir / "converted.pdf"
            else:
                _validate_image_archive(rendered, output_format)
                destination = output_dir / "converted-images.zip"
            shutil.copyfile(rendered, destination)
    except (OSError, shutil.Error) as exc:
        raise HtmlConversionError from exc
    return destination


def _validate_image_archive(archive_path: Path, image_format: str) -> None:
    suffix = ".jpg" if image_format == "jpg" else ".svg"
    try:
        with ZipFile(archive_path) as archive:
            members = archive.infolist()
            if not 1 <= len(members) <= MAX_HTML_PAGES:
                raise HtmlConversionError
            expected = [f"page-{index:03d}{suffix}" for index in range(1, len(members) + 1)]
            if (
                [item.filename for item in members] != expected
                or sum(item.file_size for item in members) > MAX_HTML_OUTPUT_BYTES
                or any(item.file_size > MAX_HTML_OUTPUT_BYTES for item in members)
                or archive.testzip() is not None
            ):
                raise HtmlConversionError
            for member in members:
                content = archive.read(member)
                if image_format == "jpg":
                    with Image.open(BytesIO(content)) as image:
                        if (
                            image.format != "JPEG"
                            or image.width * image.height > MAX_HTML_PAGE_PIXELS
                        ):
                            raise HtmlConversionError
                        image.verify()
                else:
                    root = ET.fromstring(content)
                    if root.tag.rsplit("}", 1)[-1] != "svg":
                        raise HtmlConversionError
    except (OSError, ValueError, ET.ParseError, BadZipFile) as exc:
        raise HtmlConversionError from exc
