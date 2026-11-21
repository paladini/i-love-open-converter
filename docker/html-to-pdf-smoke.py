"""Exercise the isolated HTML renderer in a Linux worker container."""

from __future__ import annotations

import base64
import tempfile
from pathlib import Path

import pymupdf
from PIL import Image

from i_love_open_converter.html_ops import (
    HtmlExternalResourceError,
    convert_html,
)

with tempfile.TemporaryDirectory(prefix="html-pdf-smoke-") as temporary:
    root = Path(temporary)
    image = Image.new("RGB", (8, 8), (40, 90, 170))
    image_bytes_path = root / "pixel.png"
    image.save(image_bytes_path, format="PNG")
    image_data = base64.b64encode(image_bytes_path.read_bytes()).decode("ascii")
    source = root / "input.html"
    output = root / "output"
    source.write_text(
        "<!doctype html><html><head><style>h1 { color: #285aaa }</style></head>"
        f'<body><h1>Local HTML conversion</h1><img src="data:image/png;base64,{image_data}">'
        "</body></html>",
        encoding="utf-8",
    )
    result = convert_html(source, output)
    with pymupdf.open(result) as document:
        if document.page_count != 1 or "Local HTML conversion" not in document[0].get_text():
            raise RuntimeError("Rendered PDF did not preserve its selectable text")
        if not document[0].get_images():
            raise RuntimeError("Embedded data URI image was not rendered")

    for resource in (
        "http://example.invalid/image.png",
        "https://example.invalid/image.png",
        "ftp://example.invalid/image.png",
        "file:///etc/passwd",
        "../assets/image.png",
    ):
        source.write_text(f'<html><body><img src="{resource}"></body></html>', encoding="utf-8")
        try:
            convert_html(source, output)
        except HtmlExternalResourceError:
            pass
        else:
            raise RuntimeError(f"Blocked resource was not rejected: {resource}")

print(
    "HTML_TO_PDF_SMOKE_OK: selectable text and data URI rendered; HTTP, HTTPS, FTP, file, "
    "and relative resources blocked"
)
