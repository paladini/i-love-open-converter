"""Exercise shipped native converters and models with local fixtures only."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from pathlib import Path

import pymupdf
from docx import Document
from PIL import Image, ImageDraw
from psd_tools import PSDImage

from i_love_open_converter.config import Settings
from i_love_open_converter.heic_ops import convert_heic_to_image
from i_love_open_converter.html_ops import convert_html
from i_love_open_converter.image_ops import process_image
from i_love_open_converter.main import create_app
from i_love_open_converter.office_ops import convert_office
from i_love_open_converter.pdf_archive import pdfa_available
from i_love_open_converter.psd_ops import convert_psd_to_image, inspect_psd
from i_love_open_converter.raw_ops import convert_raw_to_jpeg
from i_love_open_converter.worker import process_one_job

ROOT = Path("/tmp/conversion-runtime-smoke")
FIXTURES = Path("/app/smoke-fixtures")
HEIC_FIXTURE = Path(os.getenv("CONVERSION_SMOKE_HEIC_FIXTURE", str(FIXTURES / "example.heic")))
RAW_FIXTURE = Path(os.getenv("CONVERSION_SMOKE_RAW_FIXTURE", str(FIXTURES / "Canon-EOS-D60.CRW")))


async def asgi_request(app, method: str, path: str, body: bytes = b"", headers=()):
    sent = False
    messages = []

    async def receive():
        nonlocal sent
        if sent:
            await asyncio.Future()
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        messages.append(message)

    await app(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "root_path": "",
            "headers": list(headers),
            "client": ("127.0.0.1", 12345),
            "server": ("127.0.0.1", 8080),
        },
        receive,
        send,
    )
    status = next(
        message["status"] for message in messages if message["type"] == "http.response.start"
    )
    response = b"".join(
        message.get("body", b"") for message in messages if message["type"] == "http.response.body"
    )
    return status, response


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
settings = Settings(data_dir=ROOT / "pdfa-job-data")
app = create_app(settings)
boundary = "conversion-runtime-smoke"
multipart = (
    (
        f'--{boundary}\r\nContent-Disposition: form-data; name="operation"\r\n\r\npdf.pdfa\r\n'
        f'--{boundary}\r\nContent-Disposition: form-data; name="options"\r\n\r\n{{}}\r\n'
        f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="source.pdf"\r\n'
        "Content-Type: application/pdf\r\n\r\n"
    ).encode()
    + pdf_path.read_bytes()
    + f"\r\n--{boundary}--\r\n".encode()
)


async def finish_pdfa_job():
    async with app.router.lifespan_context(app):
        submitted_status, submitted_body = await asgi_request(
            app,
            "POST",
            "/api/jobs",
            multipart,
            [
                (b"content-type", f"multipart/form-data; boundary={boundary}".encode()),
                (b"content-length", str(len(multipart)).encode()),
            ],
        )
        assert submitted_status == 202, submitted_body.decode()
        submitted = json.loads(submitted_body)
        assert process_one_job(settings)
        status_code, status_body = await asgi_request(app, "GET", submitted["status_url"])
        assert status_code == 200
        status = json.loads(status_body)
        assert status["state"] == "succeeded"
        download_status, downloaded = await asgi_request(app, "GET", status["download_url"])
        assert download_status == 200
        assert downloaded, status["download_url"]
        return downloaded


download = asyncio.run(finish_pdfa_job())
pdfa_path = ROOT / "archival.pdf"
pdfa_path.write_bytes(download)
with pymupdf.open(pdfa_path) as result:
    assert result.page_count == 1 and "PDF/A smoke content" in result[0].get_text()
print("RUNTIME_SMOKE_OK: PDF/A API job was converted and independently validated")

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
