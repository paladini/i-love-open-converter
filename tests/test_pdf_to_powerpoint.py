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
from pptx.util import Inches

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

    first_slide, second_slide = presentation.slides
    assert presentation.slide_width == Inches(13.333333)
    assert abs(presentation.slide_height - Inches(240 * 13.333333 / 360)) < 1000
    first_text = next(shape for shape in first_slide.shapes
                      if shape.has_text_frame and "Editable slide one" in shape.text)
    second_text = next(shape for shape in second_slide.shapes
                       if shape.has_text_frame and "Editable slide two" in shape.text)
    expected_scale = 13.333333 / 360
    assert abs(first_text.left - Inches(48 * expected_scale)) < 1000
    second_scale = presentation.slide_height.inches / 360
    expected_second_left = (presentation.slide_width.inches - 240 * second_scale) / 2
    assert abs(second_text.left - Inches(expected_second_left + 36 * second_scale)) < 1000
    for slide in presentation.slides:
        assert all(shape.left >= 0 and shape.top >= 0
                   and shape.left + shape.width <= presentation.slide_width
                   and shape.top + shape.height <= presentation.slide_height
                   for shape in slide.shapes)
    font_size_pt = first_text.text_frame.paragraphs[0].runs[0].font.size.pt
    assert abs(font_size_pt - 11 * expected_scale * 72) < 0.1


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


def test_powerpoint_rejects_page_over_pixel_limit_without_download(settings, tmp_path, monkeypatch):
    _run_worker(monkeypatch)
    pdf = pymupdf.open()
    pdf.new_page(width=5000, height=5000)
    source = tmp_path / "oversized-page.pdf"
    pdf.save(source)
    pdf.close()
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/jobs", data={"operation": "pdf.to_powerpoint"},
            files={"files": ("oversized-page.pdf", source.read_bytes(), "application/pdf")},
        )
        assert response.status_code == 202
        assert process_one_job(settings)
        status = client.get(response.json()["status_url"]).json()
        assert status["state"] == "failed" and status["error"]["code"] == "powerpoint_failed"
        assert client.get(response.json()["status_url"] + "/download").status_code != 200


def test_powerpoint_rejects_shape_limit_without_download(settings, pdf_bytes, monkeypatch):
    _run_worker(monkeypatch)
    assert powerpoint_worker.MAX_SHAPES == 20_000
    monkeypatch.setattr(powerpoint_worker, "MAX_SHAPES", 1)
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/jobs", data={"operation": "pdf.to_powerpoint"},
            files={"files": ("input.pdf", pdf_bytes, "application/pdf")},
        )
        assert response.status_code == 202
        assert process_one_job(settings)
        status = client.get(response.json()["status_url"]).json()
        assert status["state"] == "failed" and status["error"]["code"] == "powerpoint_failed"
        assert client.get(response.json()["status_url"] + "/download").status_code != 200


def test_powerpoint_timeout_fails_without_download(settings, pdf_bytes, monkeypatch):
    monkeypatch.setattr(pdf_ops, "word_isolated", lambda: True)

    def timeout(command, **_kwargs):
        raise pdf_ops.subprocess.TimeoutExpired(command, 180)

    monkeypatch.setattr(pdf_ops.subprocess, "run", timeout)
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/jobs", data={"operation": "pdf.to_powerpoint"},
            files={"files": ("input.pdf", pdf_bytes, "application/pdf")},
        )
        assert response.status_code == 202
        assert process_one_job(settings)
        status = client.get(response.json()["status_url"]).json()
        assert status["state"] == "failed" and status["error"]["code"] == "powerpoint_failed"
        assert client.get(response.json()["status_url"] + "/download").status_code != 200


def test_powerpoint_output_limit_removes_partial_presentation(tmp_path, monkeypatch, pdf_bytes):
    monkeypatch.setattr(powerpoint_worker, "_limit_resources", lambda: None)
    monkeypatch.setattr(powerpoint_worker, "MAX_OUTPUT_BYTES", 1)
    source, destination = tmp_path / "input.pdf", tmp_path / "partial.pptx"
    source.write_bytes(pdf_bytes)
    try:
        powerpoint_worker.main(source, destination)
    except ValueError as exc:
        assert "output limit" in str(exc)
    else:
        raise AssertionError("output limit was not enforced")
    assert not destination.exists()


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
