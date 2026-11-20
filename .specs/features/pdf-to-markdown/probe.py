"""Inspect local Markdown rendering and generated image references."""

from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

import pymupdf
from PIL import Image

with TemporaryDirectory() as folder:
    root = Path(folder)
    image = BytesIO()
    Image.new("RGB", (80, 80), "red").save(image, "PNG")
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "Hello Markdown", fontsize=18)
    page.insert_image(pymupdf.Rect(72, 100, 250, 278), stream=image.getvalue())
    markdown = document.to_markdown(use_ocr=False, embed_images=True, filename="document")
    print(markdown[:300])
    print([p.name for p in root.iterdir()])
