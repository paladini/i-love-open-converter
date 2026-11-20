from io import BytesIO
from zipfile import ZipFile

import pymupdf
from fastapi.testclient import TestClient
from PIL import Image

from i_love_open_converter.main import create_app
from i_love_open_converter.worker import process_one_job


def test_pdf_to_markdown_packages_text_and_images(settings, monkeypatch):
    disabled = []
    monkeypatch.setattr("onnxruntime.disable_telemetry_events", lambda: disabled.append(True))
    image = BytesIO()
    Image.new("RGB", (80, 80), "red").save(image, "PNG")
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "First page content")
    page.insert_image(pymupdf.Rect(72, 100, 250, 278), stream=image.getvalue())
    document.new_page().insert_text((72, 72), "Second page content")
    source = document.tobytes()
    document.close()
    with TestClient(create_app(settings)) as client:
        assert client.get("/tools/pdf-to-markdown").status_code == 200
        response = client.post(
            "/api/jobs", data={"operation": "pdf.to_markdown"},
            files={"files": ("sample.pdf", source, "application/pdf")},
        )
        assert response.status_code == 202
        assert process_one_job(settings)
        assert disabled == [True]
        result = client.get(response.json()["status_url"] + "/download")
        assert result.status_code == 200
        with ZipFile(BytesIO(result.content)) as archive:
            assert archive.namelist() == ["document.md", "image-001.png"]
            text = archive.read("document.md").decode("utf-8")
            assert text.index("First page content") < text.index("Second page content")
            assert "(image-001.png)" in text and "data:image" not in text
            with Image.open(BytesIO(archive.read("image-001.png"))) as extracted:
                assert extracted.width and extracted.height


def test_pdf_to_markdown_rejects_multiple_files(settings, pdf_bytes):
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/jobs", data={"operation": "pdf.to_markdown"},
            files=[("files", ("a.pdf", pdf_bytes)), ("files", ("b.pdf", pdf_bytes))],
        )
        assert response.status_code == 422
        invalid = client.post(
            "/api/jobs", data={"operation": "pdf.to_markdown"},
            files={"files": ("invalid.pdf", b"not a pdf", "application/pdf")},
        )
        assert invalid.status_code == 422
        document = pymupdf.open()
        document.new_page()
        encrypted = document.tobytes(
            encryption=pymupdf.PDF_ENCRYPT_AES_256,
            owner_pw="owner-password", user_pw="user-password",
        )
        document.close()
        protected = client.post(
            "/api/jobs", data={"operation": "pdf.to_markdown"},
            files={"files": ("protected.pdf", encrypted, "application/pdf")},
        )
        assert protected.status_code == 422


def test_pdf_to_markdown_includes_detectable_table(settings):
    document = pymupdf.open()
    page = document.new_page()
    for x in (72, 180, 288):
        page.draw_line((x, 100), (x, 160))
    for y in (100, 130, 160):
        page.draw_line((72, y), (288, y))
    for x, y, text in [(80, 120, "Name"), (188, 120, "Count"),
                       (80, 150, "Apples"), (188, 150, "Three")]:
        page.insert_text((x, y), text)
    source = document.tobytes()
    document.close()
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/jobs", data={"operation": "pdf.to_markdown"},
            files={"files": ("table.pdf", source, "application/pdf")},
        )
        assert response.status_code == 202
        assert process_one_job(settings)
        result = client.get(response.json()["status_url"] + "/download")
        assert result.status_code == 200
        with ZipFile(BytesIO(result.content)) as archive:
            markdown = archive.read("document.md").decode("utf-8")
            assert "Apples" in markdown and "Three" in markdown and "|" in markdown
