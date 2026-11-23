from __future__ import annotations

from io import BytesIO
from zipfile import ZipFile

import pymupdf
from fastapi.testclient import TestClient

from i_love_open_converter.main import create_app
from i_love_open_converter.pdf_ops import apply_pdf_compression_profile, process_pdf
from i_love_open_converter.worker import process_one_job


def test_compression_profiles_rewrite_images_with_fixed_parameters():
    class FakeDocument:
        calls = []

        def rewrite_images(self, **kwargs):
            self.calls.append(kwargs)

    document = FakeDocument()
    apply_pdf_compression_profile(document, "lossless")
    apply_pdf_compression_profile(document, "recommended")
    apply_pdf_compression_profile(document, "extreme")

    assert document.calls == [
        {"dpi_threshold": 200, "dpi_target": 150, "quality": 75},
        {"dpi_threshold": 150, "dpi_target": 96, "quality": 45},
    ]


def test_lossy_pdf_compression_keeps_page_count_and_text(tmp_path, pdf_bytes):
    source = tmp_path / "input.pdf"
    source.write_bytes(pdf_bytes)
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    outputs, content_type = process_pdf(
        "pdf.compress", [(source, "input.pdf")], {"profile": "recommended"}, output_dir
    )

    assert content_type == "application/pdf"
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as before:
        original_text = [page.get_text() for page in before]
        original_count = before.page_count
    with pymupdf.open(outputs[0]) as after:
        assert after.page_count == original_count
        assert [page.get_text() for page in after] == original_text


def test_single_pdf_compression_keeps_pdf_download_shape(tmp_path, pdf_bytes):
    source = tmp_path / "input.pdf"
    source.write_bytes(pdf_bytes)
    output_dir = tmp_path / "output"

    outputs, content_type = process_pdf(
        "pdf.compress", [(source, "input.pdf")], {"profile": "lossless"}, output_dir
    )

    assert content_type == "application/pdf"
    assert [path.name for path in outputs] == ["compressed.pdf"]


def test_pdf_compression_api_rejects_unknown_profile(settings, pdf_bytes):
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/jobs",
            data={"operation": "pdf.compress", "options": '{"profile":"fastest"}'},
            files={"files": ("input.pdf", pdf_bytes, "application/pdf")},
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_options"


def test_batch_pdf_compression_returns_ordered_zip_with_unique_names(settings, pdf_bytes):
    second = pymupdf.open()
    second.new_page().insert_text((20, 30), "Second source")
    second_bytes = second.tobytes()
    second.close()
    with TestClient(create_app(settings)) as client:
        created = client.post(
            "/api/jobs",
            data={"operation": "pdf.compress", "options": '{"profile":"recommended"}'},
            files=[
                ("files", ("report.pdf", pdf_bytes, "application/pdf")),
                ("files", ("report.pdf", second_bytes, "application/pdf")),
            ],
        )
        assert created.status_code == 202
        assert process_one_job(settings)
        status = client.get(created.json()["status_url"]).json()
        assert status["files"][0]["name"] == "converted-files.zip"
        result = client.get(status["download_url"])

    assert result.headers["content-type"].startswith("application/zip")
    with ZipFile(BytesIO(result.content)) as archive:
        assert archive.namelist() == ["report-compressed.pdf", "report-compressed-2.pdf"]
        with pymupdf.open(stream=archive.read(archive.namelist()[0]), filetype="pdf") as first:
            assert "Test page 1" in first[0].get_text()
        with pymupdf.open(stream=archive.read(archive.namelist()[1]), filetype="pdf") as last:
            assert "Second source" in last[0].get_text()


def test_batch_pdf_compression_rejects_more_than_configured_file_limit(settings, pdf_bytes):
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/jobs",
            data={"operation": "pdf.compress", "options": "{}"},
            files=[
                ("files", (f"{index}.pdf", pdf_bytes, "application/pdf")) for index in range(11)
            ],
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "too_many_files"
