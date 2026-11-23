from __future__ import annotations

import sqlite3
from io import BytesIO
from zipfile import ZipFile

import pymupdf
from fastapi.testclient import TestClient

from i_love_open_converter.main import create_app
from i_love_open_converter.pdf_ops import process_pdf
from i_love_open_converter.worker import process_one_job


def test_single_pdf_rotation_keeps_existing_output_name(tmp_path, pdf_bytes):
    source = tmp_path / "source.pdf"
    source.write_bytes(pdf_bytes)
    output_dir = tmp_path / "output"

    outputs, content_type = process_pdf(
        "pdf.rotate", [(source, "source.pdf")], {"degrees": 90}, output_dir
    )

    assert content_type == "application/pdf"
    assert [path.name for path in outputs] == ["rotated.pdf"]


def test_batch_rotation_returns_ordered_collision_safe_zip(settings, pdf_bytes):
    second = pymupdf.open()
    second.new_page().insert_text((20, 30), "Second source")
    second_bytes = second.tobytes()
    second.close()
    with TestClient(create_app(settings)) as client:
        created = client.post(
            "/api/jobs",
            data={"operation": "pdf.rotate", "options": '{"degrees":90}'},
            files=[
                ("files", ("report.pdf", pdf_bytes, "application/pdf")),
                ("files", ("Report.pdf", second_bytes, "application/pdf")),
            ],
        )
        assert created.status_code == 202
        assert process_one_job(settings)
        status = client.get(created.json()["status_url"]).json()
        assert status["files"][0]["name"] == "converted-files.zip"
        result = client.get(status["download_url"])

    assert result.headers["content-type"].startswith("application/zip")
    with ZipFile(BytesIO(result.content)) as archive:
        assert archive.namelist() == ["report-rotated.pdf", "Report-rotated-2.pdf"]
        expected_pages = (
            ("Test page 1", "Test page 2"),
            ("Second source",),
        )
        for member, expected_texts in zip(archive.namelist(), expected_pages, strict=True):
            with pymupdf.open(stream=archive.read(member), filetype="pdf") as document:
                assert document.page_count == len(expected_texts)
                assert [page.get_text().strip() for page in document] == list(expected_texts)
                assert all(page.rotation == 90 for page in document)


def test_batch_rotation_rejects_more_than_configured_file_limit(settings, pdf_bytes):
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/jobs",
            data={"operation": "pdf.rotate", "options": '{"degrees":180}'},
            files=[
                ("files", (f"{index}.pdf", pdf_bytes, "application/pdf")) for index in range(11)
            ],
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "too_many_files"
    with sqlite3.connect(settings.database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM conversion_jobs").fetchone()[0] == 0
