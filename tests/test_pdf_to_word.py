import sqlite3
from io import BytesIO

import pymupdf
import pytest
from docx import Document
from fastapi.testclient import TestClient
from PIL import Image

from i_love_open_converter import pdf_ops
from i_love_open_converter.main import create_app
from i_love_open_converter.worker import process_one_job


def _job_count(settings):
    with sqlite3.connect(settings.database_path) as connection:
        return connection.execute("SELECT COUNT(*) FROM conversion_jobs").fetchone()[0]


def test_pdf_to_word_has_editable_text_in_order(settings, monkeypatch):
    # Test conversion separately from the deployment isolation guard.
    monkeypatch.setattr("i_love_open_converter.pdf_ops.word_isolated", lambda: True)
    pdf = pymupdf.open()
    pdf.new_page().insert_text((72, 72), "First page content")
    pdf.new_page().insert_text((72, 72), "Second page content")
    source = pdf.tobytes()
    pdf.close()
    with TestClient(create_app(settings)) as client:
        assert client.get("/tools/pdf-to-word").status_code == 200
        response = client.post(
            "/api/jobs",
            data={"operation": "pdf.to_word"},
            files={"files": ("source.pdf", source, "application/pdf")},
        )
        assert response.status_code == 202
        assert process_one_job(settings)
        result = client.get(response.json()["status_url"] + "/download")
        assert result.status_code == 200
        text = "\n".join(p.text for p in Document(BytesIO(result.content)).paragraphs)
        assert text.index("First page content") < text.index("Second page content")


def test_pdf_to_word_ocr_option_converts_searchable_intermediate(settings, monkeypatch):
    monkeypatch.setattr(pdf_ops, "word_isolated", lambda: True)

    def add_recognized_text(source, destination, language):
        assert language == "eng"
        with pymupdf.open(source) as document:
            document[0].insert_text((72, 72), "Recognized scanned words")
            document.save(destination)

    monkeypatch.setattr(pdf_ops, "make_searchable_pdf", add_recognized_text)
    pdf = pymupdf.open()
    pdf.new_page()
    source = pdf.tobytes()
    pdf.close()
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/jobs",
            data={"operation": "pdf.to_word", "options": '{"ocr":true,"language":"eng"}'},
            files={"files": ("scan.pdf", source, "application/pdf")},
        )
        assert response.status_code == 202
        assert process_one_job(settings)
        download = client.get(response.json()["status_url"] + "/download")
        assert download.status_code == 200
        text = "\n".join(p.text for p in Document(BytesIO(download.content)).paragraphs)
        assert "Recognized scanned words" in text


@pytest.mark.parametrize(
    "operation",
    ["pdf.to_word", "pdf.to_excel"],
)
def test_office_ocr_rejects_invalid_options_before_job_creation(settings, pdf_bytes, operation):
    with TestClient(create_app(settings)) as client:
        for options in (
            '{"ocr":"yes"}',
            '{"ocr":true,"language":"fra"}',
            '{"ocr":true,"language":[]}',
            '{"unknown":true}',
        ):
            response = client.post(
                "/api/jobs",
                data={"operation": operation, "options": options},
                files={"files": ("source.pdf", pdf_bytes, "application/pdf")},
            )
            assert response.status_code == 422
            assert response.json()["error"]["code"] == "invalid_options"
            assert _job_count(settings) == 0


@pytest.mark.parametrize(
    "operation",
    ["pdf.to_word", "pdf.to_excel"],
)
def test_office_ocr_page_limit_is_rejected_before_job_creation(settings, operation):
    pdf = pymupdf.open()
    for _ in range(21):
        pdf.new_page()
    source = pdf.tobytes()
    pdf.close()
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/jobs",
            data={
                "operation": operation,
                "options": '{"ocr":true,"language":"eng"}',
            },
            files={"files": ("long-scan.pdf", source, "application/pdf")},
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "page_limit_exceeded"
        assert _job_count(settings) == 0


def test_pdf_to_word_rejects_invalid_and_multiple_files(settings, pdf_bytes):
    with TestClient(create_app(settings)) as client:
        bad = client.post(
            "/api/jobs",
            data={"operation": "pdf.to_word"},
            files={"files": ("bad.pdf", b"invalid", "application/pdf")},
        )
        assert bad.status_code == 422
        multiple = client.post(
            "/api/jobs",
            data={"operation": "pdf.to_word"},
            files=[("files", ("a.pdf", pdf_bytes)), ("files", ("b.pdf", pdf_bytes))],
        )
        assert multiple.status_code == 422
        pdf = pymupdf.open()
        pdf.new_page()
        protected = pdf.tobytes(
            encryption=pymupdf.PDF_ENCRYPT_AES_256,
            owner_pw="owner-password",
            user_pw="user-password",
        )
        pdf.close()
        encrypted = client.post(
            "/api/jobs",
            data={"operation": "pdf.to_word"},
            files={"files": ("locked.pdf", protected, "application/pdf")},
        )
        assert encrypted.status_code == 422


def test_pdf_to_word_fails_safely_for_extreme_page(settings, monkeypatch):
    monkeypatch.setattr("i_love_open_converter.pdf_ops.word_isolated", lambda: True)
    pdf = pymupdf.open()
    pdf.new_page(width=5000, height=5000).insert_text((72, 72), "Large page")
    source = pdf.tobytes()
    pdf.close()
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/jobs",
            data={"operation": "pdf.to_word"},
            files={"files": ("large.pdf", source, "application/pdf")},
        )
        assert response.status_code == 202
        assert process_one_job(settings)
        status = client.get(response.json()["status_url"]).json()
        assert status["state"] == "failed" and status["error"]["code"] == "word_failed"
        assert client.get(response.json()["status_url"] + "/download").status_code != 200


def test_pdf_to_word_retains_detectable_table_and_image(settings, monkeypatch):
    monkeypatch.setattr("i_love_open_converter.pdf_ops.word_isolated", lambda: True)
    image = BytesIO()
    Image.new("RGB", (80, 80), "red").save(image, "PNG")
    pdf = pymupdf.open()
    page = pdf.new_page()
    for x in (72, 180, 288):
        page.draw_line((x, 100), (x, 160))
    for y in (100, 130, 160):
        page.draw_line((72, y), (288, y))
    for x, y, value in [
        (80, 120, "Name"),
        (188, 120, "Count"),
        (80, 150, "Apples"),
        (188, 150, "Three"),
    ]:
        page.insert_text((x, y), value)
    page.insert_image(pymupdf.Rect(72, 200, 200, 328), stream=image.getvalue())
    source = pdf.tobytes()
    pdf.close()
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/jobs",
            data={"operation": "pdf.to_word"},
            files={"files": ("table.pdf", source, "application/pdf")},
        )
        assert response.status_code == 202
        assert process_one_job(settings)
        result = client.get(response.json()["status_url"] + "/download")
        assert result.status_code == 200
        doc = Document(BytesIO(result.content))
        assert any(
            "Apples" in cell.text
            for table in doc.tables
            for row in table.rows
            for cell in row.cells
        )
        assert len(doc.inline_shapes) >= 1


def test_pdf_to_word_requires_isolated_linux_worker(settings, pdf_bytes, monkeypatch):
    monkeypatch.setattr("i_love_open_converter.pdf_ops.word_isolated", lambda: False)
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/jobs",
            data={"operation": "pdf.to_word"},
            files={"files": ("input.pdf", pdf_bytes, "application/pdf")},
        )
        assert response.status_code == 202
        assert process_one_job(settings)
        status = client.get(response.json()["status_url"]).json()
        assert status["state"] == "failed" and status["error"]["code"] == "word_unavailable"
        assert client.get(response.json()["status_url"] + "/download").status_code != 200


def test_word_isolation_requires_linux_attestation_and_loopback_only(monkeypatch):
    monkeypatch.setattr(pdf_ops.sys, "platform", "linux")
    monkeypatch.delenv("OFFICE_NETWORK_ISOLATED", raising=False)
    monkeypatch.setattr(pdf_ops.socket, "if_nameindex", lambda: [(1, "lo")])
    assert not pdf_ops.word_isolated()
    monkeypatch.setenv("OFFICE_NETWORK_ISOLATED", "1")
    assert pdf_ops.word_isolated()
    monkeypatch.setattr(pdf_ops.socket, "if_nameindex", lambda: [(1, "lo"), (2, "eth0")])
    assert not pdf_ops.word_isolated()
    monkeypatch.setattr(pdf_ops.sys, "platform", "win32")
    assert not pdf_ops.word_isolated()
