from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from io import BytesIO
from zipfile import ZipFile

import pymupdf
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from i_love_open_converter.database import claim_next_job
from i_love_open_converter.main import create_app
from i_love_open_converter.worker import (
    cleanup_expired_jobs,
    process_one_job,
    recover_interrupted_jobs,
)


def _multipart(filename: str, content: bytes, content_type: str = "image/jpeg"):
    return {"files": (filename, content, content_type)}


def test_organize_pdf_pages_and_reject_invalid_selection(settings, pdf_bytes):
    with TestClient(create_app(settings)) as client:
        assert client.get("/tools/pdf-organize").status_code == 200
        inspected = client.post(
            "/api/pdf/pages", files=_multipart("a.pdf", pdf_bytes, "application/pdf")
        )
        assert inspected.json() == {"page_count": 2}
        uploads = [
            ("files", ("a.pdf", pdf_bytes, "application/pdf")),
            ("files", ("b.pdf", pdf_bytes, "application/pdf")),
        ]
        for pages in ([], [[1, 3]], [[3, 1]], [[1, 1], [1, 1]], [[True, 1]]):
            response = client.post(
                "/api/jobs",
                data={"operation": "pdf.organize", "options": json.dumps({"pages": pages})},
                files=uploads,
            )
            assert response.status_code == 422
            assert response.json()["error"]["code"] == "invalid_options"
        response = client.post(
            "/api/jobs",
            data={
                "operation": "pdf.organize",
                "options": json.dumps({"pages": [[1, 2], [2, 1], [1, 1]]}),
            },
            files=uploads,
        )
        assert response.status_code == 202
        assert process_one_job(settings)
        download = client.get(response.json()["status_url"] + "/download")
        assert download.status_code == 200
        with pymupdf.open(stream=download.content, filetype="pdf") as document:
            assert [page.get_text().strip() for page in document] == [
                "Test page 2",
                "Test page 1",
                "Test page 1",
            ]


def test_pdf_page_inspection_rejects_non_pdf_content(settings, jpeg_bytes):
    with TestClient(create_app(settings)) as client:
        inspected = client.post(
            "/api/pdf/pages", files=_multipart("fake.pdf", jpeg_bytes, "application/pdf")
        )
        assert inspected.status_code == 422
        assert inspected.json()["error"]["code"] == "invalid_file"
        submitted = client.post(
            "/api/jobs",
            data={"operation": "pdf.organize", "options": '{"pages": [[1, 1]]}'},
            files=_multipart("fake.pdf", jpeg_bytes, "application/pdf"),
        )
        assert submitted.status_code == 422
        assert submitted.json()["error"]["code"] == "invalid_file"


def test_pdf_preview_renders_selected_page_and_rejects_invalid_input(
    settings, pdf_bytes, jpeg_bytes
):
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/pdf/preview",
            data={"page": "2"},
            files=_multipart("document.pdf", pdf_bytes, "application/pdf"),
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        with Image.open(BytesIO(response.content)) as preview:
            assert preview.size == (240, 120)
        for number in ("0", "3", "-1", "1.5"):
            result = client.post(
                "/api/pdf/preview",
                data={"page": number},
                files=_multipart("document.pdf", pdf_bytes, "application/pdf"),
            )
            assert result.status_code == 422
        invalid = client.post(
            "/api/pdf/preview", files=_multipart("fake.pdf", jpeg_bytes, "application/pdf")
        )
        assert invalid.status_code == 422
        assert invalid.json()["error"]["code"] == "invalid_file"


def test_crop_preserves_unselected_pages_and_respects_rotation(settings):
    source = pymupdf.open()
    page = source.new_page(width=300, height=200)
    page.insert_text((70, 70), "inside")
    page.set_cropbox(pymupdf.Rect(20, 10, 280, 190))
    page.set_rotation(90)
    source.new_page(width=300, height=200)
    pdf = source.tobytes()
    source.close()
    with TestClient(create_app(settings)) as client:
        for rectangle, ranges in [
            ([0, 0, 0, 1], "1"),
            ([0, 0, 2, 1], "1"),
            ([0, 0, 1, True], "1"),
            ([0, 0, 1, 1], "3"),
        ]:
            result = client.post(
                "/api/jobs",
                data={
                    "operation": "pdf.crop",
                    "options": json.dumps({"rectangle": rectangle, "ranges": ranges}),
                },
                files=_multipart("a.pdf", pdf, "application/pdf"),
            )
            assert result.status_code == 422
            assert result.json()["error"]["code"] == "invalid_options"
        result = client.post(
            "/api/jobs",
            data={
                "operation": "pdf.crop",
                "options": json.dumps({"rectangle": [0, 0, 0.5, 1], "ranges": "1"}),
            },
            files=_multipart("a.pdf", pdf, "application/pdf"),
        )
        assert result.status_code == 202
        assert process_one_job(settings)
        response = client.get(result.json()["status_url"] + "/download")
        assert response.status_code == 200
        with pymupdf.open(stream=response.content, filetype="pdf") as document:
            assert document[0].rotation == 90
            assert document[0].rect.width == pytest.approx(90)
            assert document[0].rect.height == pytest.approx(260)
            assert document[0].cropbox == pymupdf.Rect(20, 100, 280, 190)
            assert document[1].rect == pymupdf.Rect(0, 0, 300, 200)


def test_pdf_preview_limits_large_page_dimensions(settings):
    document = pymupdf.open()
    document.new_page(width=3000, height=1500)
    source = document.tobytes()
    document.close()
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/pdf/preview", files=_multipart("large.pdf", source, "application/pdf")
        )
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        with Image.open(BytesIO(response.content)) as preview:
            assert preview.size == (1000, 500)


@pytest.mark.parametrize("kind", ["text", "image", "shape", "note"])
def test_pdf_edit_adds_requested_content(settings, pdf_bytes, jpeg_bytes, kind):
    options = {
        "kind": kind,
        "page": 1,
        "rectangle": [0.1, 0.1, 0.9, 0.9],
        "color": "#ff0000",
        "font": "helv",
        "font_size": 12,
        "text": "Example note",
        "shape": "ellipse",
    }
    uploads = [("files", ("a.pdf", pdf_bytes, "application/pdf"))]
    if kind == "image":
        uploads.append(("files", ("photo.jpg", jpeg_bytes, "image/jpeg")))
    with TestClient(create_app(settings)) as client:
        invalid = client.post(
            "/api/jobs",
            data={
                "operation": "pdf.edit",
                "options": json.dumps({**options, "rectangle": [0, 0, 2, 1]}),
            },
            files=uploads,
        )
        assert invalid.status_code == 422
        result = client.post(
            "/api/jobs",
            data={"operation": "pdf.edit", "options": json.dumps(options)},
            files=uploads,
        )
        assert result.status_code == 202
        assert process_one_job(settings)
        response = client.get(result.json()["status_url"] + "/download")
        assert response.status_code == 200
        with pymupdf.open(stream=response.content, filetype="pdf") as document:
            page = document[0]
            if kind == "text":
                assert "Example note" in page.get_text()
            elif kind == "image":
                assert len(page.get_images()) == 1
            elif kind == "shape":
                assert len(page.get_drawings()) == 1
            else:
                assert list(page.annots())[0].info["content"] == "Example note"


def test_pdf_edit_accepts_webp_with_transparency(settings, pdf_bytes):
    image = BytesIO()
    Image.new("RGBA", (16, 16), (255, 0, 0, 80)).save(image, "WEBP", lossless=True)
    options = {"kind": "image", "page": 1, "rectangle": [0.1, 0.1, 0.9, 0.9], "color": "#000000"}
    uploads = [
        ("files", ("a.pdf", pdf_bytes, "application/pdf")),
        ("files", ("a.webp", image.getvalue(), "image/webp")),
    ]
    with TestClient(create_app(settings)) as client:
        result = client.post(
            "/api/jobs",
            data={"operation": "pdf.edit", "options": json.dumps(options)},
            files=uploads,
        )
        assert result.status_code == 202
        assert process_one_job(settings)
        response = client.get(result.json()["status_url"] + "/download")
        assert response.status_code == 200
        with pymupdf.open(stream=response.content, filetype="pdf") as document:
            assert document[0].get_images()[0][1] != 0


def test_password_protection_and_unlock_do_not_store_password_in_job_options(
    settings, pdf_bytes, caplog
):
    password = "long secret 123"
    with TestClient(create_app(settings)) as client:
        request = client.post(
            "/api/jobs",
            data={"operation": "pdf.protect", "password": password},
            files=_multipart("a.pdf", pdf_bytes, "application/pdf"),
        )
        assert request.status_code == 202
        job_id = request.json()["job_id"]
        with sqlite3.connect(settings.database_path) as connection:
            options = connection.execute(
                "SELECT options_json FROM conversion_jobs WHERE id = ?", (job_id,)
            ).fetchone()[0]
        assert password not in options
        assert process_one_job(settings)
        assert not (settings.jobs_dir / job_id / "secret").exists()
        protected = client.get(request.json()["status_url"] + "/download")
        assert protected.status_code == 200
        with pymupdf.open(stream=protected.content, filetype="pdf") as document:
            assert document.needs_pass
            assert not document.authenticate("wrong")
            assert document.authenticate(password)
            assert document.page_count == 2
        wrong = client.post(
            "/api/jobs",
            data={"operation": "pdf.unlock", "password": "wrong"},
            files=_multipart("protected.pdf", protected.content, "application/pdf"),
        )
        assert wrong.status_code == 422
        assert wrong.json()["error"]["code"] == "invalid_file"
        unlocked = client.post(
            "/api/jobs",
            data={"operation": "pdf.unlock", "password": password},
            files=_multipart("protected.pdf", protected.content, "application/pdf"),
        )
        assert unlocked.status_code == 202
        assert process_one_job(settings)
        output = client.get(unlocked.json()["status_url"] + "/download")
        with pymupdf.open(stream=output.content, filetype="pdf") as document:
            assert not document.needs_pass
            assert document[0].get_text().strip() == "Test page 1"
        assert password not in caplog.text


def test_visual_signature_adds_an_image_to_selected_page(settings, pdf_bytes, jpeg_bytes):
    options = {"kind": "image", "page": 2, "rectangle": [0.1, 0.1, 0.9, 0.7], "color": "#000000"}
    uploads = [
        ("files", ("source.pdf", pdf_bytes, "application/pdf")),
        ("files", ("signature.jpg", jpeg_bytes, "image/jpeg")),
    ]
    with TestClient(create_app(settings)) as client:
        page = client.get("/tools/pdf-sign")
        assert page.status_code == 200
        assert "signature" in page.text and "certificado digital" in page.text
        response = client.post(
            "/api/jobs",
            data={"operation": "pdf.sign", "options": json.dumps(options)},
            files=uploads,
        )
        assert response.status_code == 202
        assert process_one_job(settings)
        result = client.get(response.json()["status_url"] + "/download")
        assert result.status_code == 200
        with pymupdf.open(stream=result.content, filetype="pdf") as document:
            assert not document[0].get_images()
            assert len(document[1].get_images()) == 1


@pytest.mark.parametrize(
    "operation,password,code",
    [
        ("pdf.protect", "", "invalid_options"),
        ("pdf.protect", "a" * 41, "invalid_options"),
        ("pdf.unlock", "", "invalid_file"),
    ],
)
def test_password_job_rejects_missing_or_oversized_password(
    settings, pdf_bytes, operation, password, code
):
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/jobs",
            data={"operation": operation, "password": password},
            files=_multipart("a.pdf", pdf_bytes, "application/pdf"),
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == code


def test_password_job_recovers_after_interruption(settings, pdf_bytes):
    with TestClient(create_app(settings)) as client:
        submitted = client.post(
            "/api/jobs",
            data={"operation": "pdf.protect", "password": "recovery-pass"},
            files=_multipart("a.pdf", pdf_bytes, "application/pdf"),
        )
        job_id = submitted.json()["job_id"]
        assert claim_next_job(settings.database_path)["id"] == job_id
        assert recover_interrupted_jobs(settings) == 1
        assert process_one_job(settings)
        assert not (settings.jobs_dir / job_id / "secret").exists()
        assert client.get(submitted.json()["status_url"]).json()["state"] == "succeeded"


def test_redaction_removes_content_and_keeps_other_page_text(settings):
    document = pymupdf.open()
    page = document.new_page(width=200, height=200)
    page.insert_text((20, 40), "SECRET_TOKEN")
    page.insert_text((20, 150), "Keep this")
    page.draw_rect(pymupdf.Rect(20, 20, 80, 50), color=(1, 0, 0))
    source = document.tobytes()
    document.close()
    with TestClient(create_app(settings)) as client:
        for regions in (
            [],
            [{"page": 2, "rectangle": [0, 0, 1, 1]}],
            [{"page": 1, "rectangle": [0, 0, 0, 1]}],
        ):
            invalid = client.post(
                "/api/jobs",
                data={"operation": "pdf.redact", "options": json.dumps({"regions": regions})},
                files=_multipart("a.pdf", source, "application/pdf"),
            )
            assert invalid.status_code == 422
        submitted = client.post(
            "/api/jobs",
            data={
                "operation": "pdf.redact",
                "options": json.dumps({"regions": [{"page": 1, "rectangle": [0, 0, 0.6, 0.35]}]}),
            },
            files=_multipart("a.pdf", source, "application/pdf"),
        )
        assert submitted.status_code == 202
        assert process_one_job(settings)
        output = client.get(submitted.json()["status_url"] + "/download")
        assert output.status_code == 200
        with pymupdf.open(stream=output.content, filetype="pdf") as result:
            assert "SECRET_TOKEN" not in result[0].get_text()
            assert "Keep this" in result[0].get_text()
            streams = [
                result.xref_stream(xref) or b""
                for xref in range(1, result.xref_length())
                if result.xref_is_stream(xref)
            ]
            assert all(b"SECRET_TOKEN" not in stream for stream in streams)


def test_redaction_blanks_image_pixels_and_removes_overlapping_annotations(settings):
    picture = BytesIO()
    Image.new("RGB", (100, 100), (255, 0, 0)).save(picture, "PNG")
    document = pymupdf.open()
    page = document.new_page(width=100, height=100)
    page.insert_image(page.rect, stream=picture.getvalue())
    annotation = page.add_text_annot((10, 10), "sensitive comment")
    annotation.update()
    data = document.tobytes()
    document.close()
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/jobs",
            data={
                "operation": "pdf.redact",
                "options": json.dumps({"regions": [{"page": 1, "rectangle": [0, 0, 0.5, 1]}]}),
            },
            files=_multipart("a.pdf", data, "application/pdf"),
        )
        assert response.status_code == 202
        assert process_one_job(settings)
        result = client.get(response.json()["status_url"] + "/download")
        with pymupdf.open(stream=result.content, filetype="pdf") as output:
            page = output[0]
            assert not list(page.annots() or [])
            pixmap = page.get_pixmap(colorspace=pymupdf.csRGB, alpha=False)
            rendered = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
            assert rendered.getpixel((20, 60)) == (0, 0, 0)
            assert rendered.getpixel((80, 60)) == (255, 0, 0)
            for image in page.get_images():
                extracted = Image.open(BytesIO(output.extract_image(image[0])["image"])).convert(
                    "RGB"
                )
                assert extracted.getpixel((20, 60)) != (255, 0, 0)


def test_form_fields_are_listed_filled_and_unsupported_rejected(settings):
    document = pymupdf.open()
    page = document.new_page(width=300, height=300)
    for kind, name, rect, value in [
        (pymupdf.PDF_WIDGET_TYPE_TEXT, "name", (10, 10, 200, 40), "before"),
        (pymupdf.PDF_WIDGET_TYPE_CHECKBOX, "consent", (10, 60, 30, 80), "Off"),
        (pymupdf.PDF_WIDGET_TYPE_TEXT, "unchanged", (10, 100, 200, 130), "keep"),
    ]:
        widget = pymupdf.Widget()
        widget.field_type = kind
        widget.field_name = name
        widget.rect = pymupdf.Rect(rect)
        widget.field_value = value
        page.add_widget(widget)
    data = document.tobytes()
    document.close()
    with TestClient(create_app(settings)) as client:
        fields = client.post(
            "/api/pdf/fields", files=_multipart("a.pdf", data, "application/pdf")
        ).json()["fields"]
        by_name = {field["name"]: field for field in fields}
        assert by_name["name"]["value"] == "before"
        assert by_name["consent"]["value"] is False
        invalid = client.post(
            "/api/jobs",
            data={
                "operation": "pdf.forms",
                "options": json.dumps({"updates": [{"id": 999999, "value": "bad"}]}),
            },
            files=_multipart("a.pdf", data, "application/pdf"),
        )
        assert invalid.status_code == 422
        updates = [
            {"id": by_name["name"]["id"], "value": "after"},
            {"id": by_name["consent"]["id"], "value": True},
        ]
        result = client.post(
            "/api/jobs",
            data={"operation": "pdf.forms", "options": json.dumps({"updates": updates})},
            files=_multipart("a.pdf", data, "application/pdf"),
        )
        assert result.status_code == 202
        assert process_one_job(settings)
        output = client.get(result.json()["status_url"] + "/download")
        assert output.status_code == 200
        with pymupdf.open(stream=output.content, filetype="pdf") as filled:
            widgets = {widget.field_name: widget.field_value for widget in filled[0].widgets()}
            assert widgets["name"] == "after"
            assert widgets["consent"] not in (None, "Off", False)
            assert widgets["unchanged"] == "keep"


def test_readonly_form_field_is_reported_and_cannot_be_changed(settings):
    document = pymupdf.open()
    page = document.new_page()
    widget = pymupdf.Widget()
    widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
    widget.field_name = "read-only"
    widget.field_flags = pymupdf.PDF_FIELD_IS_READ_ONLY
    widget.field_value = "original"
    widget.rect = pymupdf.Rect(10, 10, 200, 40)
    page.add_widget(widget)
    data = document.tobytes()
    document.close()
    with TestClient(create_app(settings)) as client:
        field = client.post(
            "/api/pdf/fields", files=_multipart("a.pdf", data, "application/pdf")
        ).json()["fields"][0]
        assert field["type"] == "unsupported"
        result = client.post(
            "/api/jobs",
            data={
                "operation": "pdf.forms",
                "options": json.dumps({"updates": [{"id": field["id"], "value": "changed"}]}),
            },
            files=_multipart("a.pdf", data, "application/pdf"),
        )
        assert result.status_code == 422
        assert result.json()["error"]["code"] == "invalid_options"


def test_redaction_rejects_existing_pending_annotations_on_selected_page(settings):
    document = pymupdf.open()
    page = document.new_page(width=100, height=100)
    page.add_redact_annot(pymupdf.Rect(50, 50, 90, 90))
    data = document.tobytes()
    document.close()
    with TestClient(create_app(settings)) as client:
        result = client.post(
            "/api/jobs",
            data={
                "operation": "pdf.redact",
                "options": json.dumps({"regions": [{"page": 1, "rectangle": [0, 0, 0.4, 0.4]}]}),
            },
            files=_multipart("a.pdf", data, "application/pdf"),
        )
        assert result.status_code == 202
        assert process_one_job(settings)
        assert client.get(result.json()["status_url"]).json()["state"] == "failed"
        assert client.get(result.json()["status_url"] + "/download").status_code == 409


def test_home_page_has_image_and_pdf_groups_and_local_assets(settings):
    with TestClient(create_app(settings)) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "Imagens" in response.text
    assert "PDF" in response.text
    assert "image.convert" in response.text
    assert "https://" not in response.text
    assert response.text.count('class="tool-card"') + response.text.count('class="tool-card ') == 44
    assert "Fluxos de trabalho" in response.text
    assert "PDF para Markdown" in response.text
    assert "Desfocar cara" in response.text
    assert 'data-category="workflows"' in response.text
    assert 'data-category="img-optimize"' in response.text


def test_pdf_markup_tools_open_with_upload_first_screens(settings):
    with TestClient(create_app(settings)) as client:
        watermark = client.get("/tools/pdf-watermark")
        numbers = client.get("/tools/pdf-page-numbers")

    assert watermark.status_code == numbers.status_code == 200
    for response in (watermark, numbers):
        assert 'id="upload-step"' in response.text
        assert 'id="options-step" class="pdf-options" hidden' in response.text
        assert 'type="file" accept="application/pdf,.pdf"' in response.text
        assert 'data-pt="Remover arquivo"' in response.text
    assert "Inserir marca d'água em um PDF" in watermark.text
    assert "Inserir números de páginas a um PDF" in numbers.text


def test_convert_job_moves_from_queued_to_downloadable(settings, jpeg_bytes):
    with TestClient(create_app(settings)) as client:
        submitted = client.post(
            "/api/jobs",
            data={"operation": "image.convert", "options": '{"format":"PNG"}'},
            files=_multipart("paisagem.jpg", jpeg_bytes),
        )
        assert submitted.status_code == 202
        payload = submitted.json()
        assert payload["state"] == "queued"
        assert payload["status_url"] == f"/api/jobs/{payload['job_id']}"

        queued = client.get(payload["status_url"])
        assert queued.status_code == 200
        assert queued.json()["state"] == "queued"
        not_ready = client.get(f"{payload['status_url']}/download")
        assert not_ready.status_code == 409
        assert not_ready.json()["error"]["code"] == "job_not_ready"

        assert process_one_job(settings) is True
        succeeded = client.get(payload["status_url"])
        assert succeeded.status_code == 200
        assert succeeded.json()["state"] == "succeeded"
        assert succeeded.json()["files"][0]["name"] == "paisagem.png"

        download = client.get(succeeded.json()["download_url"])
        assert download.status_code == 200
        assert download.headers["content-type"] == "image/png"
        with Image.open(BytesIO(download.content)) as converted:
            assert converted.format == "PNG"
            assert converted.size == (16, 12)


def test_invalid_image_content_returns_422(settings):
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/jobs",
            data={"operation": "image.convert", "options": '{"format":"PNG"}'},
            files=_multipart("broken.jpg", b"not an image"),
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_file"


def test_unknown_image_extension_returns_415(settings):
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/jobs",
            data={"operation": "image.convert", "options": '{"format":"PNG"}'},
            files=_multipart("image.svg", b"<svg/>", "image/svg+xml"),
        )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_format"


def test_file_over_configured_limit_returns_413(settings):
    oversized_file = b"0" * (1024 * 1024 + 1)
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/jobs",
            data={"operation": "image.convert", "options": '{"format":"PNG"}'},
            files=_multipart("large.jpg", oversized_file),
        )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"


def test_per_file_limit_is_enforced_while_multipart_streams(settings):
    oversized_file = b"x" * (1024 * 1024 + 1)
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/jobs",
            data={"operation": "image.convert", "options": '{"format":"PNG"}'},
            files=_multipart("large.jpg", oversized_file),
        )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"


def test_total_upload_limit_is_enforced_while_multipart_streams(settings):
    chunk = b"x" * (800 * 1024)
    files = [("files", (f"{index}.jpg", chunk, "image/jpeg")) for index in range(3)]
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/jobs",
            data={"operation": "image.convert", "options": '{"format":"PNG"}'},
            files=files,
        )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "request_too_large"


def test_file_count_limit_is_enforced_during_multipart_parsing(settings, jpeg_bytes):
    files = [
        ("files", (f"{index}.jpg", jpeg_bytes, "image/jpeg"))
        for index in range(settings.max_files_per_job + 1)
    ]
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/jobs",
            data={"operation": "image.convert", "options": '{"format":"PNG"}'},
            files=files,
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "too_many_files"


def test_invalid_conversion_options_return_422(settings, jpeg_bytes):
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/jobs",
            data={"operation": "image.convert", "options": '{"format":"GIF"}'},
            files=_multipart("photo.jpg", jpeg_bytes),
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_options"


def test_unknown_jobs_return_404(settings):
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/jobs/00000000-0000-4000-8000-000000000000")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "job_not_found"


def test_pdf_merge_requires_multiple_files(settings, jpeg_bytes):
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/jobs",
            data={"operation": "pdf.merge", "options": "{}"},
            files=_multipart("photo.jpg", jpeg_bytes),
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_options"


def test_expired_terminal_job_is_removed_with_its_files(settings, jpeg_bytes):
    with TestClient(create_app(settings)) as client:
        submitted = client.post(
            "/api/jobs",
            data={"operation": "image.convert", "options": '{"format":"PNG"}'},
            files=_multipart("photo.jpg", jpeg_bytes),
        )
        job_id = submitted.json()["job_id"]
        assert process_one_job(settings)

    job_dir = settings.jobs_dir / job_id
    assert job_dir.exists()
    with sqlite3.connect(settings.database_path) as connection:
        expired = (datetime.now(UTC) - timedelta(hours=1)).isoformat(timespec="seconds")
        connection.execute(
            "UPDATE conversion_jobs SET expires_at = ? WHERE id = ?", (expired, job_id)
        )

    assert cleanup_expired_jobs(settings) == 1
    assert not job_dir.exists()
    with TestClient(create_app(settings)) as client:
        assert client.get(f"/api/jobs/{job_id}").status_code == 404


def test_batch_resize_returns_zip_with_aspect_ratio_preserved(settings, jpeg_bytes):
    with TestClient(create_app(settings)) as client:
        submitted = client.post(
            "/api/jobs",
            data={"operation": "image.resize", "options": '{"width":8,"format":"PNG"}'},
            files=[
                ("files", ("photo.jpg", jpeg_bytes, "image/jpeg")),
                ("files", ("photo.jpg", jpeg_bytes, "image/jpeg")),
            ],
        )
        assert submitted.status_code == 202
        assert process_one_job(settings)
        result = client.get(f"/api/jobs/{submitted.json()['job_id']}/download")

    assert result.status_code == 200
    assert result.headers["content-type"] == "application/zip"
    with ZipFile(BytesIO(result.content)) as archive:
        assert archive.namelist() == ["photo.png", "photo-2.png"]
        with Image.open(BytesIO(archive.read("photo.png"))) as resized:
            assert resized.size == (8, 6)


def test_image_rotate_is_clockwise_and_invalid_dimensions_are_rejected(settings, jpeg_bytes):
    with TestClient(create_app(settings)) as client:
        invalid = client.post(
            "/api/jobs",
            data={"operation": "image.resize", "options": '{"width":10001}'},
            files=_multipart("photo.jpg", jpeg_bytes),
        )
        assert invalid.status_code == 422
        assert invalid.json()["error"]["code"] == "invalid_options"

        submitted = client.post(
            "/api/jobs",
            data={"operation": "image.rotate", "options": '{"degrees":90}'},
            files=_multipart("photo.jpg", jpeg_bytes),
        )
        assert submitted.status_code == 202
        assert process_one_job(settings)
        result = client.get(f"/api/jobs/{submitted.json()['job_id']}/download")

    with Image.open(BytesIO(result.content)) as rotated:
        assert rotated.size == (12, 16)


def test_pdf_merge_and_page_range_split(settings, pdf_bytes):
    with TestClient(create_app(settings)) as client:
        merged = client.post(
            "/api/jobs",
            data={"operation": "pdf.merge", "options": "{}"},
            files=[
                ("files", ("one.pdf", pdf_bytes, "application/pdf")),
                ("files", ("two.pdf", pdf_bytes, "application/pdf")),
            ],
        )
        assert merged.status_code == 202
        assert process_one_job(settings)
        merged_pdf = client.get(f"/api/jobs/{merged.json()['job_id']}/download")
        with pymupdf.open(stream=merged_pdf.content, filetype="pdf") as document:
            assert document.page_count == 4

        split = client.post(
            "/api/jobs",
            data={"operation": "pdf.split", "options": '{"ranges":"2,1"}'},
            files={"files": ("two.pdf", pdf_bytes, "application/pdf")},
        )
        assert split.status_code == 202
        assert process_one_job(settings)
        split_zip = client.get(f"/api/jobs/{split.json()['job_id']}/download")
        assert split_zip.headers["content-type"] == "application/zip"
        with ZipFile(BytesIO(split_zip.content)) as archive:
            assert archive.namelist() == ["two-part-1.pdf", "two-part-2.pdf"]
            for filename in archive.namelist():
                with pymupdf.open(stream=archive.read(filename), filetype="pdf") as document:
                    assert document.page_count == 1


def test_pdf_range_validation_rotation_and_pdf_to_jpg(settings, pdf_bytes):
    with TestClient(create_app(settings)) as client:
        invalid = client.post(
            "/api/jobs",
            data={"operation": "pdf.split", "options": '{"ranges":"1-3"}'},
            files={"files": ("two.pdf", pdf_bytes, "application/pdf")},
        )
        assert invalid.status_code == 422
        assert invalid.json()["error"]["code"] == "invalid_options"

        duplicate_pdfs = client.post(
            "/api/jobs",
            data={"operation": "pdf.watermark", "options": '{"kind":"image"}'},
            files=[
                ("files", ("one.pdf", pdf_bytes, "application/pdf")),
                ("files", ("two.pdf", pdf_bytes, "application/pdf")),
            ],
        )
        assert duplicate_pdfs.status_code == 422
        assert duplicate_pdfs.json()["error"]["code"] == "too_many_files"

        overlapping = client.post(
            "/api/jobs",
            data={"operation": "pdf.split", "options": '{"ranges":"1-2,2"}'},
            files={"files": ("two.pdf", pdf_bytes, "application/pdf")},
        )
        assert overlapping.status_code == 422
        assert overlapping.json()["error"]["code"] == "invalid_options"

        rotated = client.post(
            "/api/jobs",
            data={"operation": "pdf.rotate", "options": '{"degrees":90}'},
            files={"files": ("two.pdf", pdf_bytes, "application/pdf")},
        )
        assert rotated.status_code == 202
        assert process_one_job(settings)
        rotated_pdf = client.get(f"/api/jobs/{rotated.json()['job_id']}/download")
        with pymupdf.open(stream=rotated_pdf.content, filetype="pdf") as document:
            assert [page.rotation for page in document] == [90, 90]

        rendered = client.post(
            "/api/jobs",
            data={"operation": "pdf.to_image", "options": "{}"},
            files={"files": ("two.pdf", pdf_bytes, "application/pdf")},
        )
        assert rendered.status_code == 202
        assert process_one_job(settings)
        images = client.get(f"/api/jobs/{rendered.json()['job_id']}/download")
        with ZipFile(BytesIO(images.content)) as archive:
            assert archive.namelist() == ["two-page-1.jpg", "two-page-2.jpg"]
            with Image.open(BytesIO(archive.read(archive.namelist()[0]))) as page_image:
                assert page_image.format == "JPEG"
                assert page_image.size == (500, 250)
                with pymupdf.open(stream=pdf_bytes, filetype="pdf") as source_document:
                    pixmap = source_document[0].get_pixmap(dpi=150, colorspace=pymupdf.csRGB)
                expected = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
                expected_buffer = BytesIO()
                expected.save(expected_buffer, format="JPEG", quality=85, optimize=True)
                with Image.open(BytesIO(expected_buffer.getvalue())) as expected_jpg:
                    assert page_image.quantization == expected_jpg.quantization

        compressed = client.post(
            "/api/jobs",
            data={"operation": "pdf.compress", "options": "{}"},
            files={"files": ("two.pdf", pdf_bytes, "application/pdf")},
        )
        assert compressed.status_code == 202
        assert process_one_job(settings)
        compressed_status = client.get(f"/api/jobs/{compressed.json()['job_id']}").json()
        assert compressed_status["input_size_bytes"] == len(pdf_bytes)
        compressed_pdf = client.get(compressed_status["download_url"])
        with pymupdf.open(stream=compressed_pdf.content, filetype="pdf") as document:
            assert document.page_count == 2


def test_static_images_become_a4_pdf_and_invalid_pdf_is_rejected(settings, jpeg_bytes):
    with TestClient(create_app(settings)) as client:
        created = client.post(
            "/api/jobs",
            data={"operation": "image.to_pdf", "options": "{}"},
            files=[
                ("files", ("photo.jpg", jpeg_bytes, "image/jpeg")),
                ("files", ("second.jpg", jpeg_bytes, "image/jpeg")),
            ],
        )
        assert created.status_code == 202
        assert process_one_job(settings)
        output = client.get(f"/api/jobs/{created.json()['job_id']}/download")
        with pymupdf.open(stream=output.content, filetype="pdf") as document:
            assert document.page_count == 2
            assert document[0].rect.width == 842

        invalid = client.post(
            "/api/jobs",
            data={"operation": "pdf.rotate", "options": '{"degrees":90}'},
            files={"files": ("broken.pdf", b"not a pdf", "application/pdf")},
        )
        assert invalid.status_code == 422
        assert invalid.json()["error"]["code"] == "invalid_file"


def test_pdf_text_watermark_and_page_numbers_apply_to_every_page(settings, pdf_bytes):
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as source_document:
        original_sizes = [page.rect for page in source_document]
    with TestClient(create_app(settings)) as client:
        watermarked = client.post(
            "/api/jobs",
            data={
                "operation": "pdf.watermark",
                "options": json.dumps(
                    {
                        "kind": "text",
                        "text": "CONFIDENTIAL",
                        "position": "center",
                        "opacity": 0.4,
                        "font": "helv",
                        "font_size": 24,
                        "color": "#808080",
                    }
                ),
            },
            files={"files": ("document.pdf", pdf_bytes, "application/pdf")},
        )
        assert watermarked.status_code == 202
        assert process_one_job(settings)
        status = client.get(watermarked.json()["status_url"])
        assert status.json()["state"] == "succeeded", status.json()
        watermarked_pdf = client.get(f"/api/jobs/{watermarked.json()['job_id']}/download")
        with pymupdf.open(stream=watermarked_pdf.content, filetype="pdf") as document:
            assert document.page_count == 2
            assert all("CONFIDENTIAL" in page.get_text() for page in document)
            assert all(
                f"Test page {index}" in page.get_text() for index, page in enumerate(document, 1)
            )
            assert [page.rect for page in document] == original_sizes
            for page in document:
                blocks = page.get_text("dict")["blocks"]
                spans = [
                    span
                    for block in blocks
                    for line in block.get("lines", [])
                    for span in line["spans"]
                ]
                watermark = next(span for span in spans if "CONFIDENTIAL" in span["text"])
                assert watermark["font"] == "Helvetica"
                assert watermark["size"] == pytest.approx(24)
                assert watermark["color"] == int("808080", 16)
                x0, y0, x1, y1 = watermark["bbox"]
                assert (x0 + x1) / 2 == pytest.approx(page.rect.width / 2, abs=12)
                assert (y0 + y1) / 2 == pytest.approx(page.rect.height / 2, abs=30)
                trace = page.get_texttrace()
                assert any(item.get("opacity") == pytest.approx(0.4) for item in trace)

        numbered = client.post(
            "/api/jobs",
            data={
                "operation": "pdf.page_numbers",
                "options": json.dumps(
                    {
                        "position": "bottom_right",
                        "format": "page_number_total",
                        "start": 5,
                        "font": "helv",
                        "font_size": 12,
                        "color": "#000000",
                        "language": "en",
                    }
                ),
            },
            files={"files": ("document.pdf", pdf_bytes, "application/pdf")},
        )
        assert numbered.status_code == 202
        assert process_one_job(settings)
        numbered_pdf = client.get(f"/api/jobs/{numbered.json()['job_id']}/download")
        with pymupdf.open(stream=numbered_pdf.content, filetype="pdf") as document:
            extracted = [page.get_text() for page in document]
            assert all(
                f"Test page {index}" in text for index, text in enumerate(extracted, start=1)
            )
            normalized = [" ".join(text.split()) for text in extracted]
            assert all(f"Page {index + 5} of 2" in text for index, text in enumerate(normalized))


def test_pdf_page_number_formats_and_ptbr_translation(settings, pdf_bytes):
    cases = [
        ({"format": "number", "start": 7, "language": "en"}, "7", "8"),
        ({"format": "number_total", "start": 3, "language": "en"}, "3 / 2", "4 / 2"),
        (
            {"format": "page_number_total", "start": 4, "language": "pt-BR"},
            "Página 4 de 2",
            "Página 5 de 2",
        ),
    ]
    with TestClient(create_app(settings)) as client:
        for options, first, second in cases:
            options.update(position="bottom_center", font="helv", font_size=12, color="#000000")
            submitted = client.post(
                "/api/jobs",
                data={"operation": "pdf.page_numbers", "options": json.dumps(options)},
                files={"files": ("document.pdf", pdf_bytes, "application/pdf")},
            )
            assert submitted.status_code == 202
            assert process_one_job(settings)
            result = client.get(f"/api/jobs/{submitted.json()['job_id']}/download")
            with pymupdf.open(stream=result.content, filetype="pdf") as document:
                pages = [" ".join(page.get_text().split()) for page in document]
                assert first in pages[0]
                assert second in pages[1]


@pytest.mark.parametrize(
    "operation,options",
    [
        ("pdf.watermark", {"kind": "text", "text": "   "}),
        ("pdf.watermark", {"kind": "text", "text": "ok", "position": "middle"}),
        ("pdf.watermark", {"kind": "text", "text": "ok", "opacity": 0}),
        ("pdf.watermark", {"kind": "text", "text": "ok", "font": "comic"}),
        ("pdf.watermark", {"kind": "text", "text": "ok", "font_size": 7}),
        ("pdf.watermark", {"kind": "text", "text": "ok", "color": "red"}),
        ("pdf.page_numbers", {"position": "middle", "format": "number"}),
        ("pdf.page_numbers", {"position": "bottom_center", "format": "unknown"}),
        ("pdf.page_numbers", {"position": "bottom_center", "format": "number", "start": 0}),
        ("pdf.page_numbers", {"position": "bottom_center", "format": "number", "font": "comic"}),
        ("pdf.page_numbers", {"position": "bottom_center", "format": "number", "font_size": 49}),
        ("pdf.page_numbers", {"position": "bottom_center", "format": "number", "language": "fr"}),
    ],
)
def test_pdf_operations_reject_invalid_option_ranges(settings, pdf_bytes, operation, options):
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/jobs",
            data={"operation": operation, "options": json.dumps(options)},
            files={"files": ("document.pdf", pdf_bytes, "application/pdf")},
        )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_options"


def test_pdf_image_watermark_preserves_page_count_and_rejects_invalid_options(settings, pdf_bytes):
    watermark_buffer = BytesIO()
    Image.new("RGBA", (12, 8), (240, 40, 60, 180)).save(watermark_buffer, format="PNG")
    with TestClient(create_app(settings)) as client:
        watermarked = client.post(
            "/api/jobs",
            data={
                "operation": "pdf.watermark",
                "options": json.dumps(
                    {
                        "kind": "image",
                        "position": "bottom_right",
                        "opacity": 0.5,
                    }
                ),
            },
            files=[
                ("files", ("document.pdf", pdf_bytes, "application/pdf")),
                ("files", ("stamp.png", watermark_buffer.getvalue(), "image/png")),
            ],
        )
        assert watermarked.status_code == 202
        assert process_one_job(settings)
        output = client.get(f"/api/jobs/{watermarked.json()['job_id']}/download")
        with pymupdf.open(stream=output.content, filetype="pdf") as document:
            assert document.page_count == 2
            for page in document:
                images = page.get_images(full=True)
                assert images
                assert all(image[1] > 0 for image in images)
                mask = document.extract_image(images[0][1])["image"]
                with Image.open(BytesIO(mask)) as alpha_mask:
                    assert alpha_mask.convert("L").getextrema()[1] <= 90

        invalid = client.post(
            "/api/jobs",
            data={
                "operation": "pdf.page_numbers",
                "options": '{"color":"red"}',
            },
            files={"files": ("document.pdf", pdf_bytes, "application/pdf")},
        )
        assert invalid.status_code == 422
        assert invalid.json()["error"]["code"] == "invalid_options"


def test_interrupted_processing_job_is_requeued_and_partial_output_removed(settings, jpeg_bytes):
    with TestClient(create_app(settings)) as client:
        submitted = client.post(
            "/api/jobs",
            data={"operation": "image.convert", "options": '{"format":"PNG"}'},
            files=_multipart("photo.jpg", jpeg_bytes),
        )
    job_id = submitted.json()["job_id"]
    assert claim_next_job(settings.database_path)["id"] == job_id
    output_dir = settings.jobs_dir / job_id / "output"
    output_dir.mkdir()
    (output_dir / "partial.bin").write_bytes(b"partial")

    assert recover_interrupted_jobs(settings) == 1
    assert not output_dir.exists()
    with TestClient(create_app(settings)) as client:
        assert client.get(f"/api/jobs/{job_id}").json()["state"] == "queued"
