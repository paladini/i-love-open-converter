from dataclasses import replace
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pymupdf
from fastapi.testclient import TestClient
from PIL import Image
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

from i_love_open_converter import pdf_ops, powerpoint_worker
from i_love_open_converter.main import create_app
from i_love_open_converter.worker import process_one_job


def _run_worker(monkeypatch):
    monkeypatch.setattr(pdf_ops, "word_isolated", lambda: True)
    monkeypatch.setattr(powerpoint_worker, "_limit_resources", lambda: None)

    def run(command, **_kwargs):
        try:
            powerpoint_worker.main(Path(command[-2]), Path(command[-1]))
        except Exception:
            return SimpleNamespace(returncode=1)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(pdf_ops.subprocess, "run", run)


def test_pdf_to_powerpoint_creates_editable_text_and_picture_shapes(settings, monkeypatch):
    _run_worker(monkeypatch)
    image = BytesIO()
    Image.new("RGB", (40, 24), "red").save(image, "PNG")
    pdf = pymupdf.open()
    first = pdf.new_page(width=360, height=240)
    first.insert_text((48, 72), "Editable slide one")
    first.insert_image(pymupdf.Rect(60, 100, 140, 148), stream=image.getvalue())
    second = pdf.new_page(width=240, height=360)
    second.insert_text((36, 90), "Editable slide two")
    source = pdf.tobytes()
    pdf.close()

    with TestClient(create_app(settings)) as client:
        home = client.get("/")
        assert home.status_code == 200
        assert 'href="/tools/pdf-to-powerpoint"' in home.text
        assert client.get("/tools/pdf-to-powerpoint").status_code == 200
        response = client.post(
            "/api/jobs", data={"operation": "pdf.to_powerpoint"},
            files={"files": ("source.pdf", source, "application/pdf")},
        )
        assert response.status_code == 202
        assert process_one_job(settings)
        result = client.get(response.json()["status_url"] + "/download")
        assert result.status_code == 200
        assert result.headers["content-type"].startswith(
            "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        )

    presentation = Presentation(BytesIO(result.content))
    assert len(presentation.slides) == 2
    slide_text = [[shape.text for shape in slide.shapes if shape.has_text_frame]
                  for slide in presentation.slides]
    assert any("Editable slide one" in text for text in slide_text[0])
    assert any("Editable slide two" in text for text in slide_text[1])
    assert any(shape.shape_type == MSO_SHAPE_TYPE.PICTURE
               for shape in presentation.slides[0].shapes)
    assert all(slide.shapes.title is None for slide in presentation.slides)


def test_pdf_to_powerpoint_rejects_invalid_multiple_and_encrypted_files(settings, pdf_bytes):
    with TestClient(create_app(settings)) as client:
        invalid = client.post(
            "/api/jobs", data={"operation": "pdf.to_powerpoint"},
            files={"files": ("bad.pdf", b"invalid", "application/pdf")},
        )
        assert invalid.status_code == 422
        multiple = client.post(
            "/api/jobs", data={"operation": "pdf.to_powerpoint"},
            files=[("files", ("a.pdf", pdf_bytes)), ("files", ("b.pdf", pdf_bytes))],
        )
        assert multiple.status_code == 422

        pdf = pymupdf.open()
        pdf.new_page()
        encrypted = pdf.tobytes(
            encryption=pymupdf.PDF_ENCRYPT_AES_256,
            owner_pw="owner-password", user_pw="user-password",
        )
        pdf.close()
        locked = client.post(
            "/api/jobs", data={"operation": "pdf.to_powerpoint"},
            files={"files": ("locked.pdf", encrypted, "application/pdf")},
        )
        assert locked.status_code == 422


def test_pdf_to_powerpoint_requires_network_isolated_worker(settings, pdf_bytes, monkeypatch):
    monkeypatch.setattr(pdf_ops, "word_isolated", lambda: False)
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/jobs", data={"operation": "pdf.to_powerpoint"},
            files={"files": ("input.pdf", pdf_bytes, "application/pdf")},
        )
        assert response.status_code == 202
        assert process_one_job(settings)
        status = client.get(response.json()["status_url"]).json()
        assert status["state"] == "failed"
        assert status["error"]["code"] == "powerpoint_unavailable"
        assert client.get(response.json()["status_url"] + "/download").status_code != 200


def test_powerpoint_worker_rejects_more_than_two_hundred_pages(settings, tmp_path, monkeypatch):
    _run_worker(monkeypatch)
    settings = replace(settings, max_file_size_mb=5, max_total_upload_mb=6)
    monkeypatch.setattr(powerpoint_worker, "_limit_resources", lambda: None)
    pdf = pymupdf.open()
    for _ in range(201):
        pdf.new_page(width=240, height=120)
    source = tmp_path / "too-many-pages.pdf"
    pdf.save(source)
    pdf.close()
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/jobs", data={"operation": "pdf.to_powerpoint"},
            files={"files": ("too-many-pages.pdf", source.read_bytes(), "application/pdf")},
        )
        assert response.status_code == 202
        assert process_one_job(settings)
        status = client.get(response.json()["status_url"]).json()
        assert status["state"] == "failed"
        assert status["error"]["code"] == "powerpoint_failed"
        assert client.get(response.json()["status_url"] + "/download").status_code != 200


def test_powerpoint_output_contains_slide_content_types(settings, monkeypatch, pdf_bytes, tmp_path):
    _run_worker(monkeypatch)
    pdf_path = tmp_path / "input.pdf"
    pdf_path.write_bytes(pdf_bytes)
    outputs, content_type = pdf_ops.process_pdf(
        "pdf.to_powerpoint", [(pdf_path, "input.pdf")], {}, tmp_path / "output"
    )
    assert content_type.startswith("application/vnd.openxmlformats-officedocument.presentationml")
    with ZipFile(outputs[0]) as archive:
        assert "ppt/presentation.xml" in archive.namelist()
        assert "ppt/slides/slide1.xml" in archive.namelist()


def test_scanned_image_page_is_kept_without_ocr(tmp_path, monkeypatch):
    monkeypatch.setattr(powerpoint_worker, "_limit_resources", lambda: None)
    image = BytesIO()
    Image.new("RGB", (120, 80), "white").save(image, "PNG")
    pdf = pymupdf.open()
    pdf.new_page(width=240, height=160).insert_image(
        pymupdf.Rect(0, 0, 240, 160), stream=image.getvalue()
    )
    source, destination = tmp_path / "scan.pdf", tmp_path / "scan.pptx"
    pdf.save(source)
    pdf.close()
    powerpoint_worker.main(source, destination)
    slide = Presentation(destination).slides[0]
    assert any(shape.shape_type == MSO_SHAPE_TYPE.PICTURE for shape in slide.shapes)
    assert not any(shape.has_text_frame and shape.text for shape in slide.shapes)
