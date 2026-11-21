"""Exercise the isolated HTML renderer in a Linux worker container."""

from __future__ import annotations

import base64
import io
import tempfile
from pathlib import Path
from zipfile import ZipFile

import pymupdf
from PIL import Image

from i_love_open_converter.html_ops import (
    HtmlExternalResourceError,
    HtmlImageBoundsError,
    convert_html,
    convert_html_to_images,
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

    source.write_text(
        "<!doctype html><html><head><style>"
        "@page { size: A4; margin: 10mm } .page { page-break-after: always } "
        ".page:last-child { page-break-after: auto }</style></head>"
        "<body><div class='page'>First page</div><div class='page'>Second page</div></body></html>",
        encoding="utf-8",
    )
    for image_format in ("jpg", "svg"):
        result = convert_html_to_images(source, output, image_format)
        with ZipFile(result) as archive:
            if archive.namelist() != [
                f"page-001.{image_format}",
                f"page-002.{image_format}",
            ]:
                raise RuntimeError(f"Unexpected {image_format} page names: {archive.namelist()}")
            page_bytes = archive.read(archive.namelist()[0])
            if image_format == "jpg":
                with Image.open(io.BytesIO(page_bytes)) as page_image:
                    if page_image.format != "JPEG" or page_image.info.get("dpi", (0,))[0] < 140:
                        raise RuntimeError("JPG page was not rendered at the requested resolution")
            elif not (
                page_bytes.lstrip().startswith(b"<?xml")
                or page_bytes.lstrip().startswith(b"<svg")
            ):
                raise RuntimeError("SVG page did not start with an SVG document")

    source.write_text(
        "<html><head><style>@page { size: 60in 60in; margin: 0 }</style></head>"
        "<body>Oversized page</body></html>",
        encoding="utf-8",
    )
    for image_format in ("jpg", "svg"):
        oversized_output = root / f"oversized-{image_format}"
        try:
            convert_html_to_images(source, oversized_output, image_format)
        except HtmlImageBoundsError:
            if list(oversized_output.iterdir()):
                raise RuntimeError("Oversized page left a partial output artifact") from None
        else:
            raise RuntimeError(f"Oversized page was accepted as {image_format}")

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
    "HTML_RENDERING_SMOKE_OK: PDF, multipage JPG and SVG rendered; oversized pages rejected; "
    "embedded data URI accepted; HTTP, HTTPS, FTP, file and relative resources blocked"
)
