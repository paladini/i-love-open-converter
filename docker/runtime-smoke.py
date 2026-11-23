"""Exercise shipped native converters and models with local fixtures only."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pymupdf
from docx import Document
from PIL import Image, ImageDraw
from psd_tools import PSDImage

from i_love_open_converter.heic_ops import convert_heic_to_image
from i_love_open_converter.html_ops import convert_html
from i_love_open_converter.image_ops import process_image
from i_love_open_converter.office_ops import convert_office
from i_love_open_converter.pdf_archive import convert_pdfa, pdfa_available
from i_love_open_converter.psd_ops import convert_psd_to_image, inspect_psd
from i_love_open_converter.raw_ops import convert_raw_to_jpeg

ROOT = Path("/tmp/conversion-runtime-smoke")
FIXTURES = Path("/app/smoke-fixtures")
HEIC_FIXTURE = Path(os.getenv("CONVERSION_SMOKE_HEIC_FIXTURE", str(FIXTURES / "example.heic")))
RAW_FIXTURE = Path(os.getenv("CONVERSION_SMOKE_RAW_FIXTURE", str(FIXTURES / "Canon-EOS-D60.CRW")))
if ROOT.exists():
    shutil.rmtree(ROOT)
ROOT.mkdir(parents=True, exist_ok=True)

heic = ROOT / "example.heic"
heic.write_bytes(HEIC_FIXTURE.read_bytes())
heic_jpeg = ROOT / "heic.jpg"
convert_heic_to_image(heic, heic_jpeg, "JPEG")
with Image.open(heic_jpeg) as result:
    assert result.format == "JPEG" and result.width > 0 and result.height > 0
print("RUNTIME_SMOKE_OK: HEIC decoded through isolated libheif")

raw = ROOT / "camera.crw"
raw.write_bytes(RAW_FIXTURE.read_bytes())
raw_jpeg = ROOT / "raw.jpg"
convert_raw_to_jpeg(raw, raw_jpeg, "JPEG")
with Image.open(raw_jpeg) as result:
    assert result.format == "JPEG" and result.width > 0 and result.height > 0
print("RUNTIME_SMOKE_OK: RAW decoded through isolated LibRaw")

psd_path = ROOT / "synthetic.psd"
canvas = Image.new("RGBA", (24, 18), (0, 0, 0, 0))
psd = PSDImage.frompil(canvas)
canvas.close()
layer = Image.new("RGBA", (24, 18), (0, 0, 0, 0))
ImageDraw.Draw(layer).rectangle((2, 2, 20, 14), fill=(220, 30, 40, 255))
psd.create_pixel_layer(layer, name="Visible smoke layer")
layer.close()
psd.save(psd_path)
width, height = inspect_psd(psd_path)
psd_output = ROOT / "psd.png"
convert_psd_to_image(psd_path, psd_output, "PNG", width, height)
with Image.open(psd_output) as result:
    assert result.format == "PNG" and result.size == (24, 18)
print("RUNTIME_SMOKE_OK: PSD rendered through isolated psd-tools worker")

docx_path = ROOT / "office.docx"
document = Document()
document.add_paragraph("Offline Office conversion smoke test")
document.save(docx_path)
office_output = convert_office(docx_path, ROOT / "office-output")
with pymupdf.open(office_output) as result:
    assert result.page_count == 1
    assert "Offline Office conversion smoke test" in result[0].get_text()
print("RUNTIME_SMOKE_OK: Office converted in the filesystem-restricted worker")

pdf_path = ROOT / "source.pdf"
document = pymupdf.open()
document.new_page().insert_text((40, 60), "PDF/A smoke content")
document.save(pdf_path)
document.close()
if not pdfa_available():
    raise RuntimeError("PDF/A runtime dependencies or ICC profile are unavailable")
pdfa_path = ROOT / "archival.pdf"
convert_pdfa(pdf_path, pdfa_path)
with pymupdf.open(pdfa_path) as result:
    assert result.page_count == 1 and "PDF/A smoke content" in result[0].get_text()
print("RUNTIME_SMOKE_OK: PDF/A converted and independently validated")

source_image = ROOT / "foreground.png"
image = Image.new("RGB", (96, 72), "white")
ImageDraw.Draw(image).ellipse((20, 8, 76, 66), fill=(20, 90, 180))
image.save(source_image)
background_output = ROOT / "background-removed.png"
process_image(source_image, background_output, "image.remove_background", {"format": "PNG"})
with Image.open(background_output) as result:
    assert result.format == "PNG" and result.mode == "RGBA" and result.size == (96, 72)
print("RUNTIME_SMOKE_OK: background removal loaded the bundled U2NetP model")

html_path = ROOT / "local.html"
html_path.write_text("<html><body><h1>Offline HTML smoke test</h1></body></html>", encoding="utf-8")
html_pdf = convert_html(html_path, ROOT / "html-output")
with pymupdf.open(html_pdf) as result:
    assert result.page_count == 1 and "Offline HTML smoke test" in result[0].get_text()
print("RUNTIME_SMOKE_OK: HTML rendered without network access")
shutil.rmtree(ROOT)
