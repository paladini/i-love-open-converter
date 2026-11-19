from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from io import BytesIO
from zipfile import ZipFile

import pymupdf
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


def test_home_page_has_image_and_pdf_groups_and_local_assets(settings):
    with TestClient(create_app(settings)) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "Imagens" in response.text
    assert "PDF" in response.text
    assert "image.convert" in response.text
    assert "https://" not in response.text


def test_pdf_markup_tools_open_with_upload_first_screens(settings):
    with TestClient(create_app(settings)) as client:
        watermark = client.get("/tools/pdf-watermark")
        numbers = client.get("/tools/pdf-page-numbers")

    assert watermark.status_code == numbers.status_code == 200
    for response in (watermark, numbers):
        assert 'id="upload-step"' in response.text
        assert 'id="options-step" class="pdf-options" hidden' in response.text
        assert 'type="file" accept="application/pdf,.pdf"' in response.text


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
            assert all(page.get_images() for page in document)

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
