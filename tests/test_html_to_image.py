from __future__ import annotations

import io
import json
import sqlite3
from dataclasses import replace
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from i_love_open_converter import html_ops, pdf_ops
from i_love_open_converter.html_ops import HtmlExternalResourceError
from i_love_open_converter.main import create_app
from i_love_open_converter.worker import process_one_job


def _submit(client, files, options=None):
    data = {"operation": "html.to_image"}
    if options is not None:
        data["options"] = json.dumps(options)
    return client.post("/api/jobs", data=data, files=files)


def _job_count(settings):
    with sqlite3.connect(settings.database_path) as connection:
        return connection.execute("SELECT COUNT(*) FROM conversion_jobs").fetchone()[0]


def _fake_convert(source: Path, output_dir: Path, image_format: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / "converted-images.zip"
    with ZipFile(destination, "w", ZIP_DEFLATED) as archive:
        if image_format == "jpg":
            image = Image.new("RGB", (12, 8), "navy")
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG")
            archive.writestr("page-001.jpg", buffer.getvalue())
        else:
            archive.writestr(
                "page-001.svg",
                b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>',
            )
    return destination


def test_html_to_image_page_and_catalog_are_bilingual(settings):
    with TestClient(create_app(settings)) as client:
        page = client.get("/tools/html-to-image")
        home = client.get("/")
        script = client.get("/static/js/html-to-image.js")

    assert page.status_code == 200
    assert 'accept=".html,.htm,text/html"' in page.text
    assert 'data-en="Export each page of a local HTML file as JPG or SVG.' in page.text
    assert 'option value="jpg"' in page.text
    assert 'option value="svg"' in page.text
    assert "HTML para imagem" in home.text
    assert "HTML to image" in home.text
    assert "html.to_image" in script.text


@pytest.mark.parametrize("extension", [".pdf", ".txt", ".xhtml"])
def test_html_to_image_rejects_unsupported_extensions(settings, extension):
    with TestClient(create_app(settings)) as client:
        response = _submit(
            client,
            [("files", (f"input{extension}", b"<h1>local</h1>", "text/html"))],
            {"format": "jpg"},
        )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_format"
    assert _job_count(settings) == 0


@pytest.mark.parametrize("options", [{}, {"format": "png"}, {"format": "svg", "dpi": 300}])
def test_html_to_image_rejects_invalid_format_options(settings, options):
    with TestClient(create_app(settings)) as client:
        response = _submit(
            client,
            [("files", ("input.html", b"<h1>local</h1>", "text/html"))],
            options,
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_options"
    assert _job_count(settings) == 0


def test_html_to_image_rejects_multiple_files(settings):
    files = [
        ("files", ("one.html", b"<h1>one</h1>", "text/html")),
        ("files", ("two.html", b"<h1>two</h1>", "text/html")),
    ]
    with TestClient(create_app(settings)) as client:
        response = _submit(client, files, {"format": "jpg"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_options"
    assert _job_count(settings) == 0


def test_html_to_image_enforces_ten_mib_upload_limit(settings):
    settings = replace(settings, max_file_size_mb=12, max_total_upload_mb=13)
    payload = b"a" * (html_ops.MAX_HTML_BYTES + 1)
    with TestClient(create_app(settings)) as client:
        response = _submit(
            client,
            [("files", ("large.html", payload, "text/html"))],
            {"format": "jpg"},
        )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"
    assert _job_count(settings) == 0


@pytest.mark.parametrize("image_format", ["jpg", "svg"])
def test_html_to_image_creates_numbered_zip_download(settings, monkeypatch, image_format):
    monkeypatch.setattr(pdf_ops, "convert_html_to_images", _fake_convert)
    with TestClient(create_app(settings)) as client:
        response = _submit(
            client,
            [("files", ("sample.html", b"<h1>local</h1>", "text/html"))],
            {"format": image_format},
        )
        assert response.status_code == 202
        assert process_one_job(settings)
        status = client.get(response.json()["status_url"])
        download = client.get(response.json()["status_url"] + "/download")

    assert status.json()["state"] == "succeeded"
    assert status.json()["files"][0]["name"] == "converted-images.zip"
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/zip"
    with ZipFile(io.BytesIO(download.content)) as archive:
        member = archive.namelist()[0]
        assert member == f"page-001.{image_format}"
        if image_format == "jpg":
            with Image.open(io.BytesIO(archive.read(member))) as image:
                assert image.format == "JPEG"
        else:
            assert archive.read(member).startswith(b"<svg")


def test_html_to_image_fails_without_artifact_when_external_resources_are_used(
    settings, monkeypatch
):
    def reject_resources(source, output_dir, image_format):
        raise HtmlExternalResourceError

    monkeypatch.setattr(pdf_ops, "convert_html_to_images", reject_resources)
    with TestClient(create_app(settings)) as client:
        response = _submit(
            client,
            [("files", ("remote.html", b'<img src="https://example.invalid/x.png">', "text/html"))],
            {"format": "svg"},
        )
        assert response.status_code == 202
        assert process_one_job(settings)
        status = client.get(response.json()["status_url"])
        download = client.get(response.json()["status_url"] + "/download")

    assert status.json()["state"] == "failed"
    assert status.json()["error"]["code"] == "html_external_resource"
    assert download.status_code == 409
    assert not list(settings.jobs_dir.glob("*/output/*"))


def test_image_archive_validation_rejects_wrong_names_and_malformed_svg(tmp_path):
    archive_path = tmp_path / "bad.zip"
    with ZipFile(archive_path, "w") as archive:
        archive.writestr("../page-001.svg", b"not svg")
    with pytest.raises(html_ops.HtmlConversionError):
        html_ops._validate_image_archive(archive_path, "svg")


def test_image_archive_validation_enforces_page_count_and_aggregate_bytes(tmp_path, monkeypatch):
    archive_path = tmp_path / "many.zip"
    with ZipFile(archive_path, "w") as archive:
        for index in range(1, html_ops.MAX_HTML_PAGES + 2):
            archive.writestr(
                f"page-{index:03d}.svg",
                b'<svg xmlns="http://www.w3.org/2000/svg"/>',
            )
    with pytest.raises(html_ops.HtmlConversionError):
        html_ops._validate_image_archive(archive_path, "svg")

    with ZipFile(archive_path, "w") as archive:
        archive.writestr(
            "page-001.svg",
            b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>',
        )
    monkeypatch.setattr(html_ops, "MAX_HTML_OUTPUT_BYTES", 10)
    monkeypatch.setattr(html_ops, "MAX_HTML_IMAGE_OUTPUT_BYTES", 10)
    with pytest.raises(html_ops.HtmlConversionError):
        html_ops._validate_image_archive(archive_path, "svg")


def test_image_archive_validation_rejects_oversized_jpg_dimensions(tmp_path, monkeypatch):
    archive_path = tmp_path / "large.zip"
    image = Image.new("RGB", (12, 8), "navy")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    with ZipFile(archive_path, "w") as archive:
        archive.writestr("page-001.jpg", buffer.getvalue())
    monkeypatch.setattr(html_ops, "MAX_HTML_PAGE_PIXELS", 50)
    with pytest.raises(html_ops.HtmlConversionError):
        html_ops._validate_image_archive(archive_path, "jpg")

    with ZipFile(archive_path, "w") as archive:
        archive.writestr("page-001.svg", b"<html></html>")
    with pytest.raises(html_ops.HtmlConversionError):
        html_ops._validate_image_archive(archive_path, "svg")
