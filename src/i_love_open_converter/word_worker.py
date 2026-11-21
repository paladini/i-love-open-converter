"""Convert one PDF to DOCX in a resource-bounded subprocess."""

from __future__ import annotations

import os
import platform
import sys
from pathlib import Path


def main(source: Path, destination: Path) -> None:
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["OPENBLAS_NUM_THREADS"] = "1"
    if sys.platform == "linux":
        import resource

        if platform.machine().lower() == "aarch64":
            resource.setrlimit(resource.RLIMIT_DATA, (1536 * 1024**2, 1536 * 1024**2))
        else:
            resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
        resource.setrlimit(resource.RLIMIT_CPU, (180, 180))
        resource.setrlimit(resource.RLIMIT_FSIZE, (256 * 1024**2, 256 * 1024**2))

    import cv2
    import pymupdf
    from pdf2docx import Converter

    cv2.setNumThreads(1)
    with pymupdf.open(source) as document:
        for page in document:
            width, height = page.rect.width * 150 / 72, page.rect.height * 150 / 72
            if width <= 0 or height <= 0 or width * height > 16_000_000:
                raise ValueError("PDF page exceeds the rendering limit")
    converter = Converter(str(source))
    try:
        converter.convert(
            str(destination), multi_processing=False, ignore_page_error=False, raw_exceptions=True
        )
    finally:
        converter.close()


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
