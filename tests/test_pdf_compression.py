from __future__ import annotations

import pymupdf
from fastapi.testclient import TestClient

from i_love_open_converter.main import create_app
from i_love_open_converter.pdf_ops import apply_pdf_compression_profile, process_pdf


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


def test_pdf_compression_api_rejects_unknown_profile(settings, pdf_bytes):
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/jobs",
            data={"operation": "pdf.compress", "options": '{"profile":"fastest"}'},
            files={"files": ("input.pdf", pdf_bytes, "application/pdf")},
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_options"
