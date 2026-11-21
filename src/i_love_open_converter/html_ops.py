"""Bounded, local-only HTML to PDF conversion."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pymupdf

from .office_ops import office_isolated

MAX_HTML_BYTES = 10 * 1024 * 1024
MAX_HTML_OUTPUT_BYTES = 256 * 1024 * 1024
MAX_HTML_PAGES = 100
HTML_TIMEOUT_SECONDS = 120


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
            rendered = root / "rendered.pdf"
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
            shutil.copyfile(rendered, destination)
    except (OSError, shutil.Error) as exc:
        raise HtmlConversionError from exc
    return destination
