from __future__ import annotations

import json
import sqlite3
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from i_love_open_converter import worker
from i_love_open_converter.main import create_app
from i_love_open_converter.worker import process_one_job


def _image_bytes(size=(80, 80), color=(20, 80, 200, 255), mode="RGBA"):
    buffer = BytesIO()
    Image.new(mode, size, color).save(buffer, format="PNG")
    return buffer.getvalue()


def _submit(client, sources, options):
    return client.post(
        "/api/jobs",
        data={"operation": "image.editor", "options": json.dumps(options)},
        files=[("files", (name, content, mime)) for name, content, mime in sources],
    )


def _run(settings, options, source=None):
    with TestClient(create_app(settings)) as client:
        response = _submit(
            client,
            [("photo.png", source or _image_bytes(), "image/png")],
            {"format": "PNG", **options},
        )
        assert response.status_code == 202
        assert process_one_job(settings)
        download = client.get(response.json()["status_url"] + "/download")
    assert download.status_code == 200
    return Image.open(BytesIO(download.content))


@pytest.mark.parametrize(
    ("filter_name", "expected"),
    [
        ("grayscale", lambda pixel: pixel[0] == pixel[1] == pixel[2]),
        ("sepia", lambda pixel: pixel[0] > pixel[1] > pixel[2]),
        ("invert", lambda pixel: pixel[:3] == (235, 175, 55)),
    ],
)
def test_editor_applies_local_filter_and_preserves_dimensions(settings, filter_name, expected):
    with _run(settings, {"filter": filter_name}) as result:
        assert result.size == (80, 80)
        assert expected(result.getpixel((40, 40)))


def test_editor_preserves_transparent_pixels_through_filter(settings):
    source = _image_bytes((32, 24), (10, 80, 220, 0))
    with _run(settings, {"filter": "sepia"}, source) as result:
        assert result.size == (32, 24)
        assert result.getpixel((16, 12))[3] == 0


def test_editor_draws_solid_and_double_frames_with_bounded_width(settings):
    with _run(
        settings,
        {"frame": "solid", "frame_width": 5, "frame_color": "red"},
    ) as solid:
        assert solid.size == (80, 80)
        assert solid.getpixel((0, 40))[:3] == (220, 53, 69)
        assert solid.getpixel((5, 40))[:3] == (20, 80, 200)
    with _run(
        settings,
        {"frame": "double", "frame_width": 6, "frame_color": "blue"},
    ) as double:
        assert double.getpixel((0, 40))[:3] == (59, 105, 225)
        assert double.getpixel((4, 40))[:3] == (59, 105, 225)
        assert double.getpixel((5, 40))[:3] == (20, 80, 200)


def test_editor_places_text_with_color_size_and_opacity(settings):
    with _run(
        settings,
        {
            "text": "LOCAL",
            "text_size": "large",
            "text_position": "top_left",
            "text_color": "red",
            "opacity": 35,
        },
    ) as result:
        assert result.size == (80, 80)
        pixels = list(result.crop((0, 0, 45, 30)).get_flattened_data())
        assert any(60 <= red <= 120 and green < 40 for red, green, blue, _ in pixels)
        assert not any(
            red > 200 and green < 80
            for red, green, blue, _ in result.crop((45, 0, 80, 30)).get_flattened_data()
        )


@pytest.mark.parametrize(
    ("format_name", "content_type"),
    [("PNG", "image/png"), ("JPEG", "image/jpeg"), ("WEBP", "image/webp")],
)
def test_editor_returns_selected_output_format(settings, format_name, content_type):
    with TestClient(create_app(settings)) as client:
        response = _submit(
            client,
            [("photo.png", _image_bytes(), "image/png")],
            {"format": format_name, "filter": "invert"},
        )
        assert response.status_code == 202
        assert process_one_job(settings)
        status = client.get(response.json()["status_url"])
        download = client.get(response.json()["status_url"] + "/download")

    assert status.json()["state"] == "succeeded"
    assert status.json()["files"][0]["name"].endswith(
        {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}[format_name]
    )
    assert download.headers["content-type"] == content_type
    with Image.open(BytesIO(download.content)) as result:
        assert result.size == (80, 80)


@pytest.mark.parametrize(
    "options",
    [
        {"filter": "unknown"},
        {"frame": "ornate"},
        {"text": "x" * 81},
        {"text": "caption", "text_position": "unknown"},
        {"text": "caption", "text_size": "huge"},
        {"text": "caption", "text_color": "#fff"},
        {"text": "caption", "opacity": 9},
        {"text": "caption", "opacity": 101},
        {"frame": "solid", "frame_width": 1},
        {"frame": "solid", "frame_width": 13},
        {"frame": "solid", "frame_color": "transparent"},
        {"filter": "original", "frame": "none"},
        {"filter": "invert", "format": "GIF"},
    ],
)
def test_editor_rejects_invalid_options_before_job(settings, options):
    with TestClient(create_app(settings)) as client:
        response = _submit(
            client,
            [("photo.png", _image_bytes(), "image/png")],
            options,
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_options"
    with sqlite3.connect(settings.database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM conversion_jobs").fetchone()[0] == 0


def test_editor_rejects_missing_source_in_multipart_form(settings):
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/jobs",
            files=[
                ("operation", (None, "image.editor")),
                ("options", (None, json.dumps({"filter": "grayscale"}))),
            ],
        )

    assert response.status_code == 422
    with sqlite3.connect(settings.database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM conversion_jobs").fetchone()[0] == 0


def test_editor_rejects_multiple_sources(settings):
    with TestClient(create_app(settings)) as client:
        response = _submit(
            client,
            [
                ("photo-a.png", _image_bytes(), "image/png"),
                ("photo-b.png", _image_bytes(), "image/png"),
            ],
            {"filter": "grayscale"},
        )

    assert response.status_code == 422
    with sqlite3.connect(settings.database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM conversion_jobs").fetchone()[0] == 0


def test_editor_worker_failure_has_no_downloadable_partial_file(settings, monkeypatch):
    def fail_process(*args, **kwargs):
        raise worker.InvalidImageError

    monkeypatch.setattr(worker, "process_image", fail_process)
    with TestClient(create_app(settings)) as client:
        response = _submit(
            client,
            [("photo.png", _image_bytes(), "image/png")],
            {"filter": "invert"},
        )
        assert response.status_code == 202
        assert process_one_job(settings)
        status = client.get(response.json()["status_url"])
        download = client.get(response.json()["status_url"] + "/download")

    assert status.json()["state"] == "failed"
    assert "download_url" not in status.json()
    assert download.status_code == 409
    assert not list(settings.jobs_dir.glob("*/output/*"))


def test_editor_card_and_controls_are_active_and_bilingual(settings):
    with TestClient(create_app(settings)) as client:
        page = client.get("/")

    assert 'data-tool="image.editor"' in page.text
    assert 'data-catalog-category="img-edit" data-catalog-order="6"' in page.text
    assert 'data-i18n="editorHint"' in page.text
    for field in (
        "editor-text",
        "editor-filter",
        "editor-frame",
        "editor-output",
    ):
        if field == "editor-output":
            assert 'id="output-format"' in page.text
        else:
            assert f'id="{field}"' in page.text
    assert "editorTitle" in page.text
    assert 'id="file-input"' in page.text
    assert 'type="file"' in page.text
