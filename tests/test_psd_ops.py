from __future__ import annotations

import json
import sqlite3
import sys
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from psd_tools import PSDImage

from i_love_open_converter import psd_ops
from i_love_open_converter.main import BASE_DIR, create_app
from i_love_open_converter.psd_ops import (
    InvalidPsdError,
    PsdUnavailableError,
    contains_smart_objects,
    convert_psd_to_image,
    inspect_psd,
)
from i_love_open_converter.worker import process_one_job


def _header(
    width: int = 8,
    height: int = 6,
    *,
    channels: int = 3,
    depth: int = 8,
    color_mode: int = 3,
    version: int = 1,
) -> bytes:
    return (
        b"8BPS"
        + version.to_bytes(2, "big")
        + bytes(6)
        + channels.to_bytes(2, "big")
        + height.to_bytes(4, "big")
        + width.to_bytes(4, "big")
        + depth.to_bytes(2, "big")
        + color_mode.to_bytes(2, "big")
    )


def _psd(path, *, color="red", size=(8, 6)):
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    document = PSDImage.frompil(canvas)
    canvas.close()
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    overlay.paste((255, 0, 0, 255), (0, 0, size[0] // 2, size[1]))
    document.create_pixel_layer(overlay, name="Visible pixels")
    document.save(path)
    overlay.close()
    hidden = Image.new("RGBA", size, (0, 0, 255, 255))
    hidden_layer = document.create_pixel_layer(hidden, name="Hidden blue layer")
    hidden_layer.visible = False
    document.save(path)
    hidden.close()
    return path


def _grayscale_psd(path, *, size=(8, 6)):
    canvas = Image.new("L", size, 0)
    document = PSDImage.frompil(canvas)
    canvas.close()
    overlay = Image.new("L", size, 128)
    document.create_pixel_layer(overlay, name="Visible grayscale pixels")
    document.save(path)
    overlay.close()
    return path


def _create_job(client, filename, content, output_format):
    return client.post(
        "/api/jobs",
        data={
            "operation": "image.from_psd",
            "options": json.dumps({"format": output_format}),
        },
        files={"files": (filename, content, "image/vnd.adobe.photoshop")},
    )


def test_inspect_psd_reads_bounded_header_without_parsing_payload(tmp_path):
    source = tmp_path / "header.psd"
    source.write_bytes(_header() + b"not a complete document")

    assert inspect_psd(source) == (8, 6)


@pytest.mark.parametrize(
    "header",
    [
        b"not a PSD".ljust(26, b"\0"),
        _header(version=2),
        _header(depth=16),
        _header(color_mode=4, channels=4),
        _header(width=8_000, height=8_000),
        _header(width=30_001, height=1),
    ],
)
def test_inspect_psd_rejects_unsupported_header(tmp_path, header):
    source = tmp_path / "invalid.psd"
    source.write_bytes(header)

    with pytest.raises(InvalidPsdError):
        inspect_psd(source)


@pytest.mark.parametrize("output_format", ["PNG", "JPEG", "WEBP"])
@pytest.mark.skipif(
    sys.platform != "linux", reason="PSD conversion requires the isolated Linux worker"
)
def test_psd_conversion_creates_one_bounded_raster_artifact(
    settings, tmp_path, monkeypatch, output_format
):
    source = _psd(tmp_path / "source.psd")
    monkeypatch.setattr(psd_ops, "office_isolated", lambda: True)

    with TestClient(create_app(settings)) as client:
        response = _create_job(client, "source.psd", source.read_bytes(), output_format)
        assert response.status_code == 202
        assert process_one_job(settings)
        status = client.get(response.json()["status_url"])
        download = client.get(response.json()["status_url"] + "/download")
        assert status.json()["state"] == "succeeded", status.json()
        with sqlite3.connect(settings.database_path) as connection:
            stored = connection.execute(
                "SELECT operation, options_json FROM conversion_jobs WHERE id = ?",
                (response.json()["job_id"],),
            ).fetchone()
            job_count = connection.execute("SELECT COUNT(*) FROM conversion_jobs").fetchone()[0]
        outputs = list((settings.jobs_dir / response.json()["job_id"] / "output").iterdir())

    assert stored[0] == "image.from_psd"
    assert json.loads(stored[1])["width"] == 8
    assert job_count == 1
    assert len(outputs) == 1
    assert download.status_code == 200
    assert (
        download.headers["content-type"]
        == {
            "PNG": "image/png",
            "JPEG": "image/jpeg",
            "WEBP": "image/webp",
        }[output_format]
    )
    with Image.open(BytesIO(download.content)) as output:
        assert output.format == output_format
        assert output.size == (8, 6)
        rgba = output.convert("RGBA")
        red_pixel = rgba.getpixel((0, 0))
        assert red_pixel[0] > 240 and red_pixel[1] < 15 and red_pixel[2] < 15
        assert red_pixel[3] == 255
        if output_format in {"PNG", "WEBP"}:
            assert rgba.getpixel((7, 0))[3] == 0
        if output_format == "JPEG":
            assert all(channel > 245 for channel in rgba.getpixel((7, 0))[:3])


@pytest.mark.skipif(
    sys.platform != "linux", reason="PSD conversion requires the isolated Linux worker"
)
def test_grayscale_psd_preserves_gray_values_and_opaque_alpha(settings, tmp_path, monkeypatch):
    source = _grayscale_psd(tmp_path / "grayscale.psd")
    monkeypatch.setattr(psd_ops, "office_isolated", lambda: True)

    with TestClient(create_app(settings)) as client:
        response = _create_job(client, "grayscale.psd", source.read_bytes(), "PNG")
        assert response.status_code == 202
        assert process_one_job(settings)
        download = client.get(response.json()["status_url"] + "/download")

    assert download.status_code == 200
    with Image.open(BytesIO(download.content)) as output:
        assert output.mode == "LA"
        assert output.getpixel((0, 0)) == (128, 255)


def test_psd_composite_is_stitched_from_bounded_viewports(tmp_path):
    pytest.importorskip("resource")
    from i_love_open_converter.psd_worker import (
        COMPOSITE_TILE_SIZE,
        MAX_ALLOCATION_BYTES,
        composite_in_bounded_tiles,
    )

    source = _psd(tmp_path / "tiled.psd", size=(2_049, 1_030))
    psd = PSDImage.open(source, max_alloc_bytes=MAX_ALLOCATION_BYTES)

    image = composite_in_bounded_tiles(psd, Image, tile_size=1_024)

    assert image.size == (2_049, 1_030)
    assert image.mode == "RGBA"
    assert 4 * 4 * COMPOSITE_TILE_SIZE**2 <= MAX_ALLOCATION_BYTES
    assert image.getpixel((1_023, 0)) == (255, 0, 0, 255)
    assert image.getpixel((1_024, 0)) == (255, 255, 255, 0)
    image.close()


def test_layerless_psd_uses_bounded_merged_composite_data(tmp_path):
    pytest.importorskip("resource")
    from i_love_open_converter.psd_worker import MAX_ALLOCATION_BYTES, composite_document

    source = tmp_path / "merged.psd"
    canvas = Image.new("RGB", (20, 12), (40, 50, 60))
    document = PSDImage.frompil(canvas)
    canvas.close()
    document.save(source)
    psd = PSDImage.open(source, max_alloc_bytes=MAX_ALLOCATION_BYTES)

    image = composite_document(psd, Image)

    assert len(psd) == 0
    assert image.mode == "RGB"
    assert image.size == (20, 12)
    assert image.getpixel((0, 0)) == (40, 50, 60)
    image.close()


@pytest.mark.parametrize(
    ("filename", "content", "output_format"),
    [
        ("wrong.png", _header(), "PNG"),
        ("broken.psd", b"not a PSD file".ljust(26, b"\0"), "PNG"),
        ("wrong.psd", _header(depth=16), "PNG"),
        ("too-large-canvas.psd", _header(width=8_000, height=8_000), "PNG"),
        ("drawing.psd", _header(), "GIF"),
    ],
)
def test_invalid_psd_request_is_rejected_before_job_queue(
    settings, filename, content, output_format
):
    with TestClient(create_app(settings)) as client:
        response = _create_job(client, filename, content, output_format)
        with sqlite3.connect(settings.database_path) as connection:
            count = connection.execute("SELECT COUNT(*) FROM conversion_jobs").fetchone()[0]

    assert response.status_code in {415, 422}
    assert count == 0


def test_psd_requires_exactly_one_file(settings):
    psd = _psd(settings.data_dir.parent / "single.psd")
    with TestClient(create_app(settings)) as client:
        missing = client.post(
            "/api/jobs",
            files=[
                ("operation", (None, "image.from_psd")),
                ("options", (None, '{"format":"PNG"}')),
            ],
        )
        multiple = client.post(
            "/api/jobs",
            data={"operation": "image.from_psd", "options": '{"format":"PNG"}'},
            files=[
                ("files", ("one.psd", psd.read_bytes(), "image/vnd.adobe.photoshop")),
                ("files", ("two.psd", psd.read_bytes(), "image/vnd.adobe.photoshop")),
            ],
        )
        with sqlite3.connect(settings.database_path) as connection:
            count = connection.execute("SELECT COUNT(*) FROM conversion_jobs").fetchone()[0]

    assert missing.status_code in {400, 422}
    assert multiple.status_code == 422
    assert count == 0


def test_psd_upload_over_configured_file_limit_is_rejected_before_queue(settings):
    oversized = _header() + bytes(settings.max_file_size_bytes)
    with TestClient(create_app(settings)) as client:
        response = _create_job(client, "oversized.psd", oversized, "PNG")
        with sqlite3.connect(settings.database_path) as connection:
            count = connection.execute("SELECT COUNT(*) FROM conversion_jobs").fetchone()[0]

    assert response.status_code == 413
    assert count == 0


def test_smart_object_layers_are_detected_without_reading_linked_contents():
    class Layer:
        def __init__(self, kind, children=()):
            self.kind = kind
            self.children = children

        def is_group(self):
            return self.kind == "group"

        def __iter__(self):
            return iter(self.children)

    document = [Layer("pixel"), Layer("group", [Layer("smartobject")])]

    assert contains_smart_objects(document)
    assert not contains_smart_objects([Layer("pixel")])


def test_psd_worker_rejects_smart_objects_before_compositing(tmp_path, monkeypatch):
    pytest.importorskip("resource")
    from psd_tools import PSDImage

    from i_love_open_converter import psd_worker

    events = []

    class SmartObject:
        kind = "smartobject"

        def is_group(self):
            return False

        @property
        def linked_path(self):
            raise AssertionError("linked smart-object paths must not be read")

    class Document:
        size = (8, 6)

        def __iter__(self):
            return iter([SmartObject()])

        def composite(self, **kwargs):
            raise AssertionError("smart-object documents must fail before compositing")

    monkeypatch.setattr(psd_worker.resource, "setrlimit", lambda *args: None)
    monkeypatch.setattr(psd_worker, "restrict", lambda *args, **kwargs: events.append("landlock"))
    monkeypatch.setattr(
        PSDImage,
        "open",
        staticmethod(lambda *args, **kwargs: events.append("parse") or Document()),
    )

    result = psd_worker.main(tmp_path, tmp_path / "source.psd", tmp_path / "out.png", "PNG")

    assert result == 2
    assert events == ["landlock", "parse"]
    assert not (tmp_path / "out.png").exists()


def test_psd_worker_requires_landlock_before_parsing(tmp_path, monkeypatch):
    pytest.importorskip("resource")
    from psd_tools import PSDImage

    from i_love_open_converter import psd_worker

    events = []
    limits = []
    monkeypatch.setattr(
        psd_worker.resource,
        "setrlimit",
        lambda limit, values: limits.append((limit, values)),
    )

    def reject_landlock(*args, **kwargs):
        events.append("landlock")
        raise OSError("Landlock unavailable")

    monkeypatch.setattr(psd_worker, "restrict", reject_landlock)
    monkeypatch.setattr(
        PSDImage,
        "open",
        staticmethod(lambda *args, **kwargs: events.append("parse")),
    )

    result = psd_worker.main(tmp_path, tmp_path / "source.psd", tmp_path / "out.png", "PNG")

    assert result == 77
    assert events == ["landlock"]
    assert limits == [
        (psd_worker.resource.RLIMIT_AS, (psd_worker.MAX_ADDRESS_SPACE_BYTES,) * 2),
        (psd_worker.resource.RLIMIT_CPU, (120, 120)),
        (psd_worker.resource.RLIMIT_FSIZE, (psd_worker.MAX_OUTPUT_BYTES,) * 2),
    ]


def test_psd_worker_deployment_is_network_isolated():
    import yaml

    compose_path = Path(__file__).resolve().parents[1] / "compose.yaml"
    compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    worker = compose["services"]["worker"]

    assert worker["network_mode"] == "none"
    assert worker["environment"]["OFFICE_NETWORK_ISOLATED"] == "1"


def test_psd_renderer_requires_isolated_linux_worker(tmp_path, monkeypatch):
    source = _psd(tmp_path / "source.psd")
    destination = tmp_path / "result.png"
    monkeypatch.setattr(psd_ops, "office_isolated", lambda: False)

    with pytest.raises(PsdUnavailableError):
        convert_psd_to_image(source, destination, "PNG", 8, 6)

    assert not destination.exists()


def test_truncated_psd_fails_without_download_or_partial_output(settings, monkeypatch):
    monkeypatch.setattr(psd_ops, "office_isolated", lambda: True)
    with TestClient(create_app(settings)) as client:
        response = _create_job(client, "truncated.psd", _header(), "PNG")
        assert response.status_code == 202
        assert process_one_job(settings)
        status = client.get(response.json()["status_url"])
        download = client.get(response.json()["status_url"] + "/download")

    assert status.json()["state"] == "failed"
    assert download.status_code == 409
    output_dir = settings.jobs_dir / response.json()["job_id"] / "output"
    assert not output_dir.exists()


def test_psd_tool_is_available_in_catalog_and_single_file_form(settings):
    with TestClient(create_app(settings)) as client:
        page = client.get("/")

    assert 'data-tool="image.from_psd"' in page.text
    assert 'data-i18n="fromPsdTitle">Converter de PSD' in page.text
    assert 'data-option="psd-note"' in page.text
    script = (BASE_DIR / "static" / "js" / "app.js").read_text(encoding="utf-8")
    assert 'fromPsdTitle: "Convert from PSD"' in script
    assert 'fromPsdNote: "PSD files are flattened into one image locally.' in script
    assert 'psdFileTypes: "PSD · RGB or grayscale, 8-bit · up to {maxFileMb} MB · 40 MP"' in script
    portuguese_file_types = (
        'psdFileTypes: "PSD · RGB ou escala de cinza, 8 bits · até {maxFileMb} MB · 40 MP"'
    )
    assert portuguese_file_types in script
    assert '".psd,image/vnd.adobe.photoshop"' in script
    assert 'operation !== "image.from_psd"' in script
    assert ': ["PNG", "JPEG", "WEBP"]' in script
