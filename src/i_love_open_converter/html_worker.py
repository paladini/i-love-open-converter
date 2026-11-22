"""Render one local HTML file to PDF inside a Landlock and resource-bounded child."""

from __future__ import annotations

import math
import os
import resource
import sys
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from .office_sandbox import restrict


def main(root: Path, source: Path, destination: Path, output_format: str = "pdf") -> int:
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["OPENBLAS_NUM_THREADS"] = "1"
    try:
        resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
        resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
        resource.setrlimit(resource.RLIMIT_FSIZE, (256 * 1024**2, 256 * 1024**2))
        restrict(root, allow_app=True)
    except (OSError, ValueError):
        return 77

    import pymupdf
    from PIL import Image
    from weasyprint import HTML
    from weasyprint.urls import FatalURLFetchingError, URLFetcher

    from .html_ops import (
        HTML_IMAGE_DPI,
        MAX_HTML_IMAGE_OUTPUT_BYTES,
        MAX_HTML_PAGE_PIXELS,
        MAX_HTML_PAGES,
        allowed_html_resource,
    )

    class DataOnlyFetcher(URLFetcher):
        def fetch(self, url: str, headers: dict[str, str] | None = None):
            if not allowed_html_resource(url):
                raise FatalURLFetchingError("Only embedded data URI resources are supported")
            return super().fetch(url, headers)

    try:
        document = HTML(filename=str(source), url_fetcher=DataOnlyFetcher()).render()
        if not 1 <= len(document.pages) <= MAX_HTML_PAGES:
            return 5 if output_format in {"jpg", "svg", "png", "jpeg", "webp"} else 2
        if output_format == "pdf":
            document.write_pdf(str(destination))
        elif output_format in {"jpg", "svg", "png", "jpeg", "webp"}:
            pdf_path = root / "rendered.pdf"
            document.write_pdf(str(pdf_path))
            with pymupdf.open(pdf_path) as pdf:
                if output_format in {"png", "jpeg", "webp"}:
                    if len(pdf) != 1:
                        return 5
                    page = pdf[0]
                    width = math.ceil(page.rect.width * 96 / 72)
                    height = math.ceil(page.rect.height * 96 / 72)
                    if width <= 0 or height <= 0 or width * height > MAX_HTML_PAGE_PIXELS:
                        return 5
                    pixels = page.get_pixmap(dpi=96, alpha=True)
                    with Image.open(BytesIO(pixels.tobytes("png"))) as rendered:
                        if output_format == "jpeg":
                            opaque = Image.new("RGB", rendered.size, "white")
                            opaque.paste(rendered, mask=rendered.getchannel("A"))
                            opaque.save(destination, format="JPEG", quality=92, optimize=True)
                            opaque.close()
                        elif output_format == "webp":
                            rendered.save(destination, format="WEBP", quality=90, method=4)
                        else:
                            rendered.save(destination, format="PNG", optimize=False)
                    if destination.stat().st_size > MAX_HTML_IMAGE_OUTPUT_BYTES:
                        return 5
                else:
                    with ZipFile(destination, "w", ZIP_DEFLATED, compresslevel=6) as archive:
                        total_bytes = 0
                        for index, page in enumerate(pdf, start=1):
                            name = f"page-{index:03d}.{output_format}"
                            width = math.ceil(page.rect.width * HTML_IMAGE_DPI / 72)
                            height = math.ceil(page.rect.height * HTML_IMAGE_DPI / 72)
                            if width <= 0 or height <= 0 or width * height > MAX_HTML_PAGE_PIXELS:
                                return 5
                            if output_format == "jpg":
                                image_path = root / name
                                page.get_pixmap(dpi=HTML_IMAGE_DPI, alpha=False).save(image_path)
                                size = image_path.stat().st_size
                                if total_bytes + size > MAX_HTML_IMAGE_OUTPUT_BYTES:
                                    return 5
                                total_bytes += size
                                archive.write(image_path, arcname=name)
                                image_path.unlink()
                            else:
                                svg = page.get_svg_image(text_as_path=True).encode("utf-8")
                                if total_bytes + len(svg) > MAX_HTML_IMAGE_OUTPUT_BYTES:
                                    return 5
                                total_bytes += len(svg)
                                archive.writestr(name, svg)
        else:
            return 2
    except FatalURLFetchingError:
        return 4
    except Exception:
        return 1
    return 0


if __name__ == "__main__":
    output_format = sys.argv[4] if len(sys.argv) > 4 else "pdf"
    raise SystemExit(main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), output_format))
