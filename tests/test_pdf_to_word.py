from io import BytesIO

import pymupdf
from docx import Document
from fastapi.testclient import TestClient
from PIL import Image

from i_love_open_converter.main import create_app
from i_love_open_converter.worker import process_one_job


def test_pdf_to_word_has_editable_text_in_order(settings):
    pdf = pymupdf.open()
    pdf.new_page().insert_text((72, 72), "First page content")
    pdf.new_page().insert_text((72, 72), "Second page content")
    source = pdf.tobytes()
    pdf.close()
    with TestClient(create_app(settings)) as client:
        assert client.get("/tools/pdf-to-word").status_code == 200
        response = client.post(
            "/api/jobs", data={"operation": "pdf.to_word"},
            files={"files": ("source.pdf", source, "application/pdf")},
        )
        assert response.status_code == 202
        assert process_one_job(settings)
        result = client.get(response.json()["status_url"] + "/download")
        assert result.status_code == 200
        text = "\n".join(p.text for p in Document(BytesIO(result.content)).paragraphs)
        assert text.index("First page content") < text.index("Second page content")


def test_pdf_to_word_rejects_invalid_and_multiple_files(settings, pdf_bytes):
    with TestClient(create_app(settings)) as client:
        bad = client.post(
            "/api/jobs", data={"operation": "pdf.to_word"},
            files={"files": ("bad.pdf", b"invalid", "application/pdf")},
        )
        assert bad.status_code == 422
        multiple = client.post(
            "/api/jobs", data={"operation": "pdf.to_word"},
            files=[("files", ("a.pdf", pdf_bytes)), ("files", ("b.pdf", pdf_bytes))],
        )
        assert multiple.status_code == 422
        pdf = pymupdf.open()
        pdf.new_page()
        protected = pdf.tobytes(
            encryption=pymupdf.PDF_ENCRYPT_AES_256,
            owner_pw="owner-password", user_pw="user-password",
        )
        pdf.close()
        encrypted = client.post(
            "/api/jobs", data={"operation": "pdf.to_word"},
            files={"files": ("locked.pdf", protected, "application/pdf")},
        )
        assert encrypted.status_code == 422


def test_pdf_to_word_fails_safely_for_extreme_page(settings):
    pdf = pymupdf.open()
    pdf.new_page(width=5000, height=5000).insert_text((72, 72), "Large page")
    source = pdf.tobytes()
    pdf.close()
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/jobs", data={"operation": "pdf.to_word"},
            files={"files": ("large.pdf", source, "application/pdf")},
        )
        assert response.status_code == 202
        assert process_one_job(settings)
        status = client.get(response.json()["status_url"]).json()
        assert status["state"] == "failed" and status["error"]["code"] == "word_failed"
        assert client.get(response.json()["status_url"] + "/download").status_code != 200


def test_pdf_to_word_retains_detectable_table_and_image(settings):
    image = BytesIO()
    Image.new("RGB", (80, 80), "red").save(image, "PNG")
    pdf = pymupdf.open()
    page = pdf.new_page()
    for x in (72, 180, 288):
        page.draw_line((x, 100), (x, 160))
    for y in (100, 130, 160):
        page.draw_line((72, y), (288, y))
    for x, y, value in [(80, 120, "Name"), (188, 120, "Count"),
                        (80, 150, "Apples"), (188, 150, "Three")]:
        page.insert_text((x, y), value)
    page.insert_image(pymupdf.Rect(72, 200, 200, 328), stream=image.getvalue())
    source = pdf.tobytes()
    pdf.close()
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/jobs", data={"operation": "pdf.to_word"},
            files={"files": ("table.pdf", source, "application/pdf")},
        )
        assert response.status_code == 202
        assert process_one_job(settings)
        result = client.get(response.json()["status_url"] + "/download")
        assert result.status_code == 200
        doc = Document(BytesIO(result.content))
        assert any("Apples" in cell.text for table in doc.tables for row in table.rows
                   for cell in row.cells)
        assert len(doc.inline_shapes) >= 1
