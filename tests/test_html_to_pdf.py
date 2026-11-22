from __future__ import annotations

import json
import sqlite3
import subprocess
from dataclasses import replace
from pathlib import Path

import pymupdf
import pytest
from fastapi.testclient import TestClient

from i_love_open_converter import html_ops, pdf_ops
from i_love_open_converter import main as main_module
from i_love_open_converter.database import get_job
from i_love_open_converter.html_ops import HtmlExternalResourceError
from i_love_open_converter.main import create_app
from i_love_open_converter.worker import process_one_job


def _submit(client, files, options=None):
    data = {"operation": "html.to_pdf"}
    if options is not None:
        data["options"] = json.dumps(options)
    return client.post("/api/jobs", data=data, files=files)


def _job_count(settings):
    with sqlite3.connect(settings.database_path) as connection:
        return connection.execute("SELECT COUNT(*) FROM conversion_jobs").fetchone()[0]


def _fake_convert(source: Path, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / "converted.pdf"
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), source.read_text(encoding="utf-8").strip())
    document.save(destination)
    document.close()
    return destination


def test_html_to_pdf_page_is_bilingual_and_explains_local_resource_limits(settings):
    with TestClient(create_app(settings)) as client:
        page = client.get("/tools/html-to-pdf")
        home = client.get("/")
        script = client.get("/static/js/html-to-pdf.js")

    assert page.status_code == 200
    assert 'accept=".html,.htm,text/html"' in page.text
    assert 'value="url"' in page.text
    assert "Public URL" in page.text
    assert "JavaScript and login pages are unsupported" in page.text
    assert "HTML local" in home.text
    assert "HTML to PDF" in home.text
    assert "html.to_pdf" in script.text
    assert "html_external_resource" in script.text


@pytest.mark.parametrize("extension", [".pdf", ".txt", ".xhtml"])
def test_html_to_pdf_rejects_unsupported_extensions_before_job_creation(settings, extension):
    with TestClient(create_app(settings)) as client:
        response = _submit(
            client,
            [("files", (f"input{extension}", b"<h1>Local</h1>", "text/html"))],
        )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_format"
    assert _job_count(settings) == 0


def test_html_to_pdf_rejects_multiple_files_and_options_before_job_creation(settings):
    with TestClient(create_app(settings)) as client:
        multiple = _submit(
            client,
            [
                ("files", ("one.html", b"<h1>One</h1>", "text/html")),
                ("files", ("two.html", b"<h1>Two</h1>", "text/html")),
            ],
        )
        options = _submit(
            client,
            [("files", ("one.html", b"<h1>One</h1>", "text/html"))],
            {"url": "https://example.invalid"},
        )

    assert multiple.status_code == 422
    assert options.status_code == 422
    assert _job_count(settings) == 0


def test_html_to_pdf_enforces_ten_mib_limit_during_upload(settings):
    settings = replace(settings, max_file_size_mb=12, max_total_upload_mb=13)
    payload = b"a" * (html_ops.MAX_HTML_BYTES + 1)
    with TestClient(create_app(settings)) as client:
        response = _submit(client, [("files", ("large.html", payload, "text/html"))])

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"
    assert _job_count(settings) == 0


def test_html_to_pdf_creates_pdf_artifact_and_downloads_it(settings, monkeypatch):
    monkeypatch.setattr(pdf_ops, "convert_html", _fake_convert)
    with TestClient(create_app(settings)) as client:
        response = _submit(
            client,
            [("files", ("sample.html", b"Local HTML content", "text/html"))],
        )
        assert response.status_code == 202, response.text
        assert process_one_job(settings)
        status = client.get(response.json()["status_url"])
        download = client.get(response.json()["status_url"] + "/download")

    assert status.json()["state"] == "succeeded"
    assert status.json()["files"][0]["name"] == "converted.pdf"
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/pdf"
    with pymupdf.open(stream=download.content, filetype="pdf") as document:
        assert document.page_count == 1
        assert "Local HTML content" in document[0].get_text()


def test_html_to_pdf_captures_public_url_without_persisting_the_url(settings, monkeypatch):
    requested = []
    monkeypatch.setattr(
        main_module,
        "fetch_public_html",
        lambda url: requested.append(url) or b"<h1>Public page</h1>",
    )
    monkeypatch.setattr(pdf_ops, "convert_html", _fake_convert)
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/jobs",
            data={"operation": "html.to_pdf", "url": "https://public.example/page?token=secret"},
            files={"multipart-marker": ("marker.txt", b"x", "text/plain")},
        )
        assert response.status_code == 202
        job = get_job(settings.database_path, response.json()["job_id"])
        assert job["options"] == {}
        assert job["artifacts"][0]["name"] == "website.html"
        stored_html = (settings.data_dir / job["artifacts"][0]["relative_path"]).read_bytes()
        assert b"Public page" in stored_html
        assert process_one_job(settings)
        status = client.get(response.json()["status_url"])

    assert requested == ["https://public.example/page?token=secret"]
    assert status.json()["state"] == "succeeded"
    assert "secret" not in str(job)


def test_html_to_pdf_url_fetch_failure_creates_no_job(settings, monkeypatch):
    def reject_url(_url):
        raise main_module.UrlSnapshotError

    monkeypatch.setattr(main_module, "fetch_public_html", reject_url)
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/jobs",
            data={"operation": "html.to_pdf", "url": "http://127.0.0.1/admin"},
            files={"multipart-marker": ("marker.txt", b"x", "text/plain")},
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_file", response.text
    assert _job_count(settings) == 0


def test_html_to_pdf_marks_blocked_resources_failed_without_download(settings, monkeypatch):
    def reject_resources(source, output_dir):
        raise HtmlExternalResourceError

    monkeypatch.setattr(pdf_ops, "convert_html", reject_resources)
    with TestClient(create_app(settings)) as client:
        response = _submit(
            client,
            [("files", ("remote.html", b'<img src="https://example.invalid/a.png">', "text/html"))],
        )
        assert response.status_code == 202
        assert process_one_job(settings)
        status = client.get(response.json()["status_url"])
        download = client.get(response.json()["status_url"] + "/download")

    assert status.json()["state"] == "failed"
    assert status.json()["error"]["code"] == "html_external_resource"
    assert download.status_code == 409
    assert not list(settings.jobs_dir.glob("*/output/*"))


def test_html_resource_policy_allows_only_embedded_data_uris():
    assert html_ops.allowed_html_resource("data:image/png;base64,AAAA")
    assert html_ops.allowed_html_resource("DATA:text/css,body%7Bcolor:black%7D")
    for url in (
        "https://example.invalid/style.css",
        "http://127.0.0.1/admin",
        "ftp://example.invalid/image.png",
        "file:///etc/passwd",
        "../assets/logo.png",
    ):
        assert not html_ops.allowed_html_resource(url)


def test_html_worker_unavailable_fails_closed_without_output(settings, monkeypatch):
    monkeypatch.setattr(html_ops, "office_isolated", lambda: False)
    with TestClient(create_app(settings)) as client:
        response = _submit(
            client,
            [("files", ("sample.html", b"<h1>Local</h1>", "text/html"))],
        )
        assert response.status_code == 202
        assert process_one_job(settings)
        status = client.get(response.json()["status_url"])
        download = client.get(response.json()["status_url"] + "/download")

    assert status.json()["state"] == "failed"
    assert status.json()["error"]["code"] == "html_unavailable"
    assert download.status_code == 409
    assert not list(settings.jobs_dir.glob("*/output/*"))


@pytest.mark.parametrize("failure", ["timeout", "invalid_pdf", "oversized_pdf", "too_many_pages"])
def test_html_worker_rejects_renderer_bounds_without_output(settings, monkeypatch, failure):
    monkeypatch.setattr(html_ops, "office_isolated", lambda: True)

    def fake_run(command, **kwargs):
        if failure == "timeout":
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])

        output_path = Path(command[-1])
        if failure == "invalid_pdf":
            output_path.write_bytes(b"not a PDF")
        else:
            document = pymupdf.open()
            for _ in range(2 if failure == "too_many_pages" else 1):
                document.new_page()
            document.save(output_path)
            document.close()
            if failure == "oversized_pdf":
                monkeypatch.setattr(html_ops, "MAX_HTML_OUTPUT_BYTES", 10)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(html_ops.subprocess, "run", fake_run)
    if failure == "too_many_pages":
        monkeypatch.setattr(html_ops, "MAX_HTML_PAGES", 1)

    with TestClient(create_app(settings)) as client:
        response = _submit(
            client,
            [("files", ("sample.html", b"<h1>Local</h1>", "text/html"))],
        )
        assert response.status_code == 202
        assert process_one_job(settings)
        status = client.get(response.json()["status_url"])
        download = client.get(response.json()["status_url"] + "/download")

    assert status.json()["state"] == "failed"
    assert status.json()["error"]["code"] == "html_failed"
    assert download.status_code == 409
    assert not list(settings.jobs_dir.glob("*/output/*"))
