from __future__ import annotations

import tempfile
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw, ImageFont

from i_love_open_converter.ocr_ops import make_searchable_pdf

with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    image_path = root / "scan.png"
    source = root / "scan.pdf"
    destination = root / "searchable.pdf"

    image = Image.new("RGB", (1400, 300), "white")
    ImageDraw.Draw(image).text(
        (60, 80),
        "Documento de teste OCR 2026",
        font=ImageFont.truetype("/usr/share/fonts/opentype/urw-base35/NimbusSans-Regular.otf", 54),
        fill="black",
    )
    image.save(image_path)

    document = pymupdf.open()
    scanned_page = document.new_page(width=1400, height=300)
    scanned_page.insert_image(scanned_page.rect, filename=str(image_path))
    existing_text_page = document.new_page(width=420, height=200)
    existing_text_page.insert_text((32, 70), "Texto existente preservado")
    source_appearance = [
        page.get_pixmap(colorspace=pymupdf.csRGB, alpha=False).samples for page in document
    ]
    document.save(source)
    document.close()

    make_searchable_pdf(source, destination, "por+eng")
    result = pymupdf.open(destination)
    recognized = result[0].get_text("text").strip()
    preserved = result[1].get_text("text").strip()
    result_appearance = [
        page.get_pixmap(colorspace=pymupdf.csRGB, alpha=False).samples for page in result
    ]
    assert result.page_count == 2
    assert "Documento" in recognized and "OCR" in recognized
    assert preserved == "Texto existente preservado"
    assert source_appearance == result_appearance
    result.close()

print("OCR_SMOKE_OK: scanned text recognized; existing text and page appearance preserved")
