from __future__ import annotations

import json
import sqlite3
from io import BytesIO
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from i_love_open_converter.main import create_app
from i_love_open_converter.worker import process_one_job


def _image_bytes(format_name, size, color):
    buffer = BytesIO()
    Image.new("RGBA" if format_name == "PNG" else "RGB", size, color).save(
        buffer, format=format_name
    )
    return buffer.getvalue()


def _submit(client, sources, options, overlay=None):
    files = [("files", (name, content, mime)) for name, content, mime in sources]
    if overlay:
        files.append(("watermark_image", overlay))
    return client.post(
        "/api/jobs",
        data={"operation": "image.watermark", "options": json.dumps(options)},
        files=files,
    )


def test_text_watermark_is_applied_at_selected_position_and_opacity(settings):
    source = _image_bytes("PNG", (120, 80), "blue")
    with TestClient(create_app(settings)) as client:
        response = _submit(
            client,
            [("photo.png", source, "image/png")],
            {
                "kind": "text",
                "text": "SAMPLE",
                "position": "bottom_right",
                "opacity": 100,
                "format": "PNG",
            },
        )
        assert response.status_code == 202
        assert process_one_job(settings)
        download = client.get(response.json()["status_url"] + "/download")

    with Image.open(BytesIO(download.content)) as result:
        assert result.size == (120, 80)
        assert result.getpixel((0, 0)) == (0, 0, 255, 255)
        assert any(
            pixel[:3] != (0, 0, 255)
            for pixel in result.crop((65, 50, 120, 80)).get_flattened_data()
        )


def test_image_overlay_batch_is_reused_but_not_returned_as_output(settings):
    sources = [
        ("first.png", _image_bytes("PNG", (100, 80), (0, 0, 255, 255)), "image/png"),
        ("second.png", _image_bytes("PNG", (80, 100), (0, 0, 255, 255)), "image/png"),
    ]
    overlay = ("logo.png", _image_bytes("PNG", (16, 16), (255, 0, 0, 255)), "image/png")
    with TestClient(create_app(settings)) as client:
        response = _submit(
            client,
            sources,
            {"kind": "image", "position": "bottom_right", "opacity": 100, "format": "PNG"},
            overlay,
        )
        assert response.status_code == 202
        assert process_one_job(settings)
        download = client.get(response.json()["status_url"] + "/download")

    with ZipFile(BytesIO(download.content)) as archive:
        assert archive.namelist() == ["first.png", "second.png"]
        with Image.open(BytesIO(archive.read("first.png"))) as first:
            assert first.getpixel((82, 62))[:3] == (255, 0, 0)
            assert first.getpixel((40, 40))[:3] == (0, 0, 255)
        with Image.open(BytesIO(archive.read("second.png"))) as second:
            assert second.size == (80, 100)


def test_image_overlay_opacity_is_applied(settings):
    source = _image_bytes("PNG", (80, 80), (0, 0, 255, 255))
    overlay = ("logo.png", _image_bytes("PNG", (8, 8), (255, 0, 0, 255)), "image/png")
    with TestClient(create_app(settings)) as client:
        response = _submit(
            client,
            [("photo.png", source, "image/png")],
            {"kind": "image", "position": "center", "opacity": 10, "format": "PNG"},
            overlay,
        )
        assert response.status_code == 202
        assert process_one_job(settings)
        download = client.get(response.json()["status_url"] + "/download")

    with Image.open(BytesIO(download.content)) as result:
        red, green, blue, alpha = result.getpixel((40, 40))
        assert 15 <= red <= 45
        assert green == 0 and blue >= 210 and alpha == 255


@pytest.mark.parametrize(
    ("options", "overlay", "expected_code"),
    [
        (
            {"kind": "text", "text": " ", "position": "center", "opacity": 50},
            None,
            "invalid_options",
        ),
        (
            {"kind": "text", "text": "x", "position": "unknown", "opacity": 50},
            None,
            "invalid_options",
        ),
        (
            {"kind": "text", "text": "x", "position": "center", "opacity": 9},
            None,
            "invalid_options",
        ),
        ({"kind": "image", "position": "center", "opacity": 50}, None, "invalid_options"),
        (
            {"kind": "image", "position": "center", "opacity": 50},
            ("logo.tif", _image_bytes("TIFF", (4, 4), "red"), "image/tiff"),
            "unsupported_format",
        ),
    ],
)
def test_watermark_rejects_invalid_options_or_overlay_before_job(
    settings, options, overlay, expected_code
):
    with TestClient(create_app(settings)) as client:
        response = _submit(
            client,
            [("photo.png", _image_bytes("PNG", (8, 8), "blue"), "image/png")],
            options,
            overlay,
        )

    assert response.status_code in {415, 422}
    assert response.json()["error"]["code"] == expected_code
    with sqlite3.connect(settings.database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM conversion_jobs").fetchone()[0] == 0


def test_image_watermark_catalog_and_mode_controls_are_active(settings):
    with TestClient(create_app(settings)) as client:
        page = client.get("/")

    assert 'data-tool="image.watermark"' in page.text
    assert "watermark-kind" in page.text
    assert "watermark-text" in page.text
    assert "watermark-image" in page.text
    assert "watermark-position" in page.text
    assert "watermark-opacity" in page.text
