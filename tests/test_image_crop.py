from __future__ import annotations

import json
import sqlite3
from io import BytesIO
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from i_love_open_converter.image_ops import (
    InvalidImageOptionsError,
    process_image,
)
from i_love_open_converter.main import create_app
from i_love_open_converter.worker import process_one_job


def _png(size, color):
    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


def test_crop_applies_exif_orientation_before_pixel_coordinates(tmp_path):
    source = tmp_path / "oriented.png"
    destination = tmp_path / "crop.png"
    image = Image.new("RGB", (3, 2))
    image.putdata(
        [
            (255, 0, 0), (0, 255, 0), (0, 0, 255),
            (255, 255, 0), (255, 0, 255), (0, 0, 0),
        ]
    )
    exif = Image.Exif()
    exif[274] = 6
    image.save(source, format="PNG", exif=exif)

    process_image(
        source,
        destination,
        "image.crop",
        {"left": 0, "top": 0, "width": 2, "height": 1, "format": "PNG"},
    )

    with Image.open(destination) as result:
        assert result.size == (2, 1)
        assert list(result.get_flattened_data()) == [(255, 255, 0), (255, 0, 0)]


@pytest.mark.parametrize(
    ("format_name", "extension", "mime_type", "pillow_format"),
    [
        ("JPEG", "jpg", "image/jpeg", "JPEG"),
        ("WEBP", "webp", "image/webp", "WEBP"),
    ],
)
def test_crop_honors_jpeg_and_webp_output_formats(
    tmp_path, format_name, extension, mime_type, pillow_format
):
    source, destination = tmp_path / "input.png", tmp_path / f"crop.{extension}"
    Image.new("RGB", (4, 3), "purple").save(source)

    content_type, _ = process_image(
        source,
        destination,
        "image.crop",
        {"left": 0, "top": 0, "width": 2, "height": 1, "format": format_name, "quality": 45},
    )

    assert content_type == mime_type
    with Image.open(destination) as result:
        assert result.format == pillow_format
        assert result.size == (2, 1)


def test_crop_applies_selected_jpeg_quality(tmp_path):
    source = tmp_path / "noise.png"
    low_quality, high_quality = tmp_path / "low.jpg", tmp_path / "high.jpg"
    Image.effect_noise((128, 128), 90).convert("RGB").save(source)
    crop = {"left": 0, "top": 0, "width": 128, "height": 128, "format": "JPEG"}

    process_image(source, low_quality, "image.crop", {**crop, "quality": 25})
    process_image(source, high_quality, "image.crop", {**crop, "quality": 90})

    with Image.open(low_quality) as low, Image.open(high_quality) as high:
        assert sum(low.quantization[0]) > sum(high.quantization[0])


@pytest.mark.parametrize(
    "options",
    [
        {"top": 0, "width": 1, "height": 1},
        {"left": 0, "top": 0, "width": 0, "height": 1},
        {"left": 0, "top": 0, "width": 1.5, "height": 1},
        {"left": -1, "top": 0, "width": 1, "height": 1},
        {"left": 10_000, "top": 0, "width": 1, "height": 1},
        {"left": 0, "top": 0, "width": 10_001, "height": 1},
    ],
)
def test_crop_rejects_malformed_coordinates_before_creating_a_job(settings, options):
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/jobs",
            data={"operation": "image.crop", "options": json.dumps(options)},
            files={"files": ("image.png", _png((4, 3), "red"), "image/png")},
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_options"
    with sqlite3.connect(settings.database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM conversion_jobs").fetchone()[0] == 0


def test_crop_batch_returns_ordered_images_in_a_zip(settings):
    with TestClient(create_app(settings)) as client:
        home = client.get("/")
        assert home.status_code == 200
        assert 'data-tool="image.crop"' in home.text
        assert "crop-left" in home.text and "crop-height" in home.text
        response = client.post(
            "/api/jobs",
            data={
                "operation": "image.crop",
                "options": json.dumps(
                    {"left": 1, "top": 1, "width": 2, "height": 1, "format": "PNG"}
                ),
            },
            files=[
                ("files", ("first.png", _png((4, 3), "red"), "image/png")),
                ("files", ("second.png", _png((5, 4), "blue"), "image/png")),
            ],
        )
        assert response.status_code == 202
        assert process_one_job(settings)
        download = client.get(response.json()["status_url"] + "/download")
        assert download.status_code == 200
        assert download.headers["content-type"].startswith("application/zip")

    with ZipFile(BytesIO(download.content)) as archive:
        assert archive.namelist() == ["first.png", "second.png"]
        for name, color in (("first.png", (255, 0, 0)), ("second.png", (0, 0, 255))):
            with Image.open(BytesIO(archive.read(name))) as image:
                assert image.size == (2, 1)
                assert list(image.get_flattened_data()) == [color, color]


def test_crop_fails_without_partial_download_when_any_batch_image_is_too_small(settings):
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/jobs",
            data={
                "operation": "image.crop",
                "options": json.dumps(
                    {"left": 1, "top": 1, "width": 2, "height": 1, "format": "PNG"}
                ),
            },
            files=[
                ("files", ("first.png", _png((4, 3), "red"), "image/png")),
                ("files", ("too-small.png", _png((2, 1), "blue"), "image/png")),
            ],
        )
        assert response.status_code == 202
        assert process_one_job(settings)
        status = client.get(response.json()["status_url"]).json()
        assert status["state"] == "failed"
        assert status["error"]["code"] == "crop_out_of_bounds"
        assert client.get(response.json()["status_url"] + "/download").status_code == 409
        assert not (settings.jobs_dir / response.json()["job_id"] / "output").exists()


def test_crop_worker_rejects_out_of_bounds_rectangle(tmp_path):
    source, destination = tmp_path / "input.png", tmp_path / "output.png"
    Image.new("RGB", (3, 2), "red").save(source)

    with pytest.raises(InvalidImageOptionsError):
        process_image(
            source,
            destination,
            "image.crop",
            {"left": 2, "top": 0, "width": 2, "height": 1, "format": "PNG"},
        )

    assert not destination.exists()
