from __future__ import annotations

import json
import sqlite3
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from i_love_open_converter import image_ops
from i_love_open_converter.image_ops import InvalidImageError, create_animated_gif
from i_love_open_converter.main import create_app
from i_love_open_converter.worker import process_one_job


def _jpeg(size, color):
    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, format="JPEG", quality=100)
    return buffer.getvalue()


def _create_job(client, files, output_format):
    return client.post(
        "/api/jobs",
        data={
            "operation": "image.from_jpg",
            "options": json.dumps({"format": output_format}),
        },
        files=[("files", file) for file in files],
    )


def test_single_jpeg_converts_to_png_with_source_dimensions(settings):
    with TestClient(create_app(settings)) as client:
        response = _create_job(client, [("source.jpg", _jpeg((13, 7), "red"), "image/jpeg")], "PNG")
        assert response.status_code == 202
        assert process_one_job(settings)
        download = client.get(response.json()["status_url"] + "/download")

    assert download.status_code == 200
    assert download.headers["content-type"] == "image/png"
    with Image.open(BytesIO(download.content)) as image:
        assert image.format == "PNG"
        assert image.size == (13, 7)


def test_jpeg_batch_to_png_returns_ordered_sanitized_zip(settings):
    with TestClient(create_app(settings)) as client:
        response = _create_job(
            client,
            [
                ("first?.jpg", _jpeg((8, 6), "red"), "image/jpeg"),
                ("second.jpg", _jpeg((9, 5), "blue"), "image/jpeg"),
            ],
            "PNG",
        )
        assert response.status_code == 202
        assert process_one_job(settings)
        download = client.get(response.json()["status_url"] + "/download")

    with ZipFile(BytesIO(download.content)) as archive:
        assert archive.namelist() == ["first_.png", "second.png"]
        with Image.open(BytesIO(archive.read("first_.png"))) as first:
            assert first.size == (8, 6)
        with Image.open(BytesIO(archive.read("second.png"))) as second:
            assert second.size == (9, 5)


def test_multiple_jpegs_create_ordered_animation_with_fixed_canvas(settings):
    with TestClient(create_app(settings)) as client:
        response = _create_job(
            client,
            [
                ("wide.jpg", _jpeg((4, 2), "red"), "image/jpeg"),
                ("tall.jpg", _jpeg((2, 4), "blue"), "image/jpeg"),
            ],
            "GIF",
        )
        assert response.status_code == 202
        assert process_one_job(settings)
        download = client.get(response.json()["status_url"] + "/download")

    assert download.status_code == 200
    assert download.headers["content-type"] == "image/gif"
    with Image.open(BytesIO(download.content)) as animation:
        assert animation.size == (4, 4)
        assert animation.n_frames == 2
        assert animation.info["duration"] == 500
        assert animation.info["loop"] == 0
        animation.seek(0)
        first = animation.convert("RGB")
        assert first.getpixel((0, 0)) == (255, 255, 255)
        assert first.getpixel((1, 1))[0] > 180
        animation.seek(1)
        second = animation.convert("RGB")
        assert second.getpixel((0, 0)) == (255, 255, 255)
        assert second.getpixel((1, 0))[2] > 180


def test_one_jpeg_with_gif_output_creates_one_frame(settings):
    with TestClient(create_app(settings)) as client:
        response = _create_job(client, [("one.jpg", _jpeg((3, 2), "green"), "image/jpeg")], "GIF")
        assert response.status_code == 202
        assert process_one_job(settings)
        download = client.get(response.json()["status_url"] + "/download")

    with Image.open(BytesIO(download.content)) as animation:
        assert animation.format == "GIF"
        assert animation.n_frames == 1
        assert animation.info["duration"] == 500
        assert animation.info["loop"] == 0


def test_gif_animation_rejects_aggregate_pixel_limit(tmp_path, monkeypatch):
    first, second = tmp_path / "first.jpg", tmp_path / "second.jpg"
    Image.new("RGB", (4, 4), "red").save(first)
    Image.new("RGB", (4, 4), "blue").save(second)
    monkeypatch.setattr(image_ops, "MAX_GIF_ANIMATION_PIXELS", 20)
    monkeypatch.setattr(
        Image.Image,
        "load",
        lambda *_args, **_kwargs: pytest.fail("pixel decoding must follow the aggregate limit"),
    )
    destination = tmp_path / "animation.gif"

    with pytest.raises(InvalidImageError):
        create_animated_gif([first, second], destination)

    assert not destination.exists()


def test_oversized_gif_job_fails_without_download(settings, monkeypatch):
    monkeypatch.setattr(image_ops, "MAX_GIF_ANIMATION_PIXELS", 20)
    with TestClient(create_app(settings)) as client:
        response = _create_job(
            client,
            [
                ("first.jpg", _jpeg((4, 4), "red"), "image/jpeg"),
                ("second.jpg", _jpeg((4, 4), "blue"), "image/jpeg"),
            ],
            "GIF",
        )
        assert response.status_code == 202
        assert process_one_job(settings)
        status_url = response.json()["status_url"]
        status = client.get(status_url).json()
        assert status["state"] == "failed"
        assert status["error"]["code"] == "invalid_file"
        assert client.get(status_url + "/download").status_code == 409

    output_dir = settings.jobs_dir / response.json()["job_id"] / "output"
    assert not output_dir.exists()


def test_from_jpg_rejects_non_jpeg_content_before_creating_a_job(settings):
    png = BytesIO()
    Image.new("RGB", (4, 4), "red").save(png, format="PNG")
    with TestClient(create_app(settings)) as client:
        response = _create_job(client, [("fake.jpg", png.getvalue(), "image/jpeg")], "PNG")

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_format"
    with sqlite3.connect(settings.database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM conversion_jobs").fetchone()[0] == 0


def test_from_jpg_rejects_images_over_pixel_limit_before_creating_a_job(
    settings, tmp_path, monkeypatch
):
    source = tmp_path / "large.jpg"
    Image.new("RGB", (11, 11), "red").save(source, format="JPEG")
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 50)

    with TestClient(create_app(settings)) as client:
        response = _create_job(client, [("large.jpg", source.read_bytes(), "image/jpeg")], "PNG")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_file"
    with sqlite3.connect(settings.database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM conversion_jobs").fetchone()[0] == 0


@pytest.mark.parametrize("format_name", ["JPEG", "WEBP", "BMP", "bad"])
def test_from_jpg_rejects_unsupported_output_format(settings, format_name):
    with TestClient(create_app(settings)) as client:
        response = _create_job(
            client, [("source.jpg", _jpeg((4, 4), "red"), "image/jpeg")], format_name
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_options"


def test_from_jpg_rejects_malformed_options_before_creating_job(settings):
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/jobs",
            data={"operation": "image.from_jpg", "options": "{"},
            files={"files": ("source.jpg", _jpeg((4, 4), "red"), "image/jpeg")},
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_options"
    with sqlite3.connect(settings.database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM conversion_jobs").fetchone()[0] == 0


def test_gif_output_rejects_more_than_ten_jpegs(settings):
    with TestClient(create_app(settings)) as client:
        response = _create_job(
            client,
            [(f"{index}.jpg", _jpeg((2, 2), "red"), "image/jpeg") for index in range(11)],
            "GIF",
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "too_many_files"
    with sqlite3.connect(settings.database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM conversion_jobs").fetchone()[0] == 0


def test_from_jpg_catalog_has_correct_filter_and_format_choices(settings):
    with TestClient(create_app(settings)) as client:
        page = client.get("/")

    assert 'data-tool="image.from_jpg"' in page.text
    js = Path("src/i_love_open_converter/static/js/app.js").read_text(encoding="utf-8")
    assert '".jpg,.jpeg,image/jpeg"' in js
    assert 'value="PNG" data-format-for="image.convert,image.from_jpg' in page.text
    assert 'value="GIF" data-format-for="image.from_jpg"' in page.text
