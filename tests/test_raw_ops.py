from __future__ import annotations

import json
import sqlite3
import sys
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from i_love_open_converter import main as app_main
from i_love_open_converter import raw_ops
from i_love_open_converter.database import get_job
from i_love_open_converter.main import create_app
from i_love_open_converter.raw_ops import (
    InvalidRawError,
    RawConversionError,
    RawImageTooLargeError,
    RawUnavailableError,
    convert_raw_to_jpeg,
)
from i_love_open_converter.worker import process_one_job

RAW_FIXTURE = Path(__file__).parent / "fixtures" / "raw" / "Canon-EOS-D60.CRW"


class _FakeProcess:
    def __init__(self, command: list[str], returncode: int = 0) -> None:
        self.command = command
        self.returncode = returncode

    def wait(self, timeout: int) -> None:
        output_path = Path(self.command[-1])
        if self.returncode == 0:
            output_path.write_bytes(b"\xff\xd8\xffjpeg")


def test_convert_raw_launches_isolated_child_and_returns_jpeg(tmp_path, monkeypatch):
    source = tmp_path / "camera.cr2"
    source.write_bytes(b"camera raw data")
    destination = tmp_path / "output.jpg"
    calls = []

    def fake_popen(command, **kwargs):
        calls.append((command, kwargs))
        return _FakeProcess(command)

    monkeypatch.setattr(raw_ops, "office_isolated", lambda: True)
    monkeypatch.setattr(raw_ops.subprocess, "Popen", fake_popen)

    content_type, size = convert_raw_to_jpeg(source, destination, "JPEG")

    command, options = calls[0]
    assert content_type == "image/jpeg"
    assert size == destination.stat().st_size
    assert destination.read_bytes().startswith(b"\xff\xd8\xff")
    assert "i_love_open_converter.raw_worker" in command
    assert options["start_new_session"] is True
    assert options["stdin"] is raw_ops.subprocess.DEVNULL
    assert options["stdout"] is raw_ops.subprocess.DEVNULL
    assert options["stderr"] is raw_ops.subprocess.DEVNULL
    assert options["env"]["HOME"] == command[-3]


@pytest.mark.parametrize(
    "returncode,error",
    [
        (2, RawConversionError),
        (3, RawImageTooLargeError),
        (4, InvalidRawError),
        (77, RawUnavailableError),
    ],
)
def test_convert_raw_maps_child_failures_and_removes_partial_output(
    tmp_path, monkeypatch, returncode, error
):
    source = tmp_path / "camera.cr2"
    source.write_bytes(b"camera raw data")
    destination = tmp_path / "output.jpg"
    destination.write_bytes(b"old output")
    monkeypatch.setattr(raw_ops, "office_isolated", lambda: True)
    monkeypatch.setattr(
        raw_ops.subprocess,
        "Popen",
        lambda command, **kwargs: _FakeProcess(command, returncode),
    )

    with pytest.raises(error):
        convert_raw_to_jpeg(source, destination, "JPEG")

    assert not destination.exists()


@pytest.mark.parametrize(
    "source_suffix,image_format,error",
    [
        (".jpg", "JPEG", InvalidRawError),
        (".cr2", "PNG", InvalidRawError),
        (".cr2", "JPEG", RawUnavailableError),
    ],
)
def test_convert_raw_rejects_invalid_input_or_unavailable_isolation(
    tmp_path, monkeypatch, source_suffix, image_format, error
):
    source = tmp_path / f"camera{source_suffix}"
    source.write_bytes(b"camera raw data")
    destination = tmp_path / "output.jpg"
    monkeypatch.setattr(raw_ops, "office_isolated", lambda: image_format == "PNG")

    with pytest.raises(error):
        convert_raw_to_jpeg(source, destination, image_format)

    assert not destination.exists()


def _submit(client: TestClient, filenames: list[str], options: dict | None = None):
    files = [
        ("files", (filename, b"not decoded in the API", "application/octet-stream"))
        for filename in filenames
    ]
    return client.post(
        "/api/jobs",
        data={
            "operation": "image.from_raw",
            "options": json.dumps(options if options is not None else {"format": "JPEG"}),
        },
        files=files,
    )


@pytest.mark.parametrize("extension", sorted(raw_ops.RAW_EXTENSIONS))
def test_raw_api_queues_each_listed_extension(settings, extension):
    with TestClient(create_app(settings)) as client:
        response = _submit(client, [f"camera{extension}"])

    assert response.status_code == 202


def test_raw_api_defaults_to_jpeg_without_quality(settings):
    with TestClient(create_app(settings)) as client:
        response = _submit(client, ["camera.cr2"], options={})
        job = get_job(settings.database_path, response.json()["job_id"])

    assert response.status_code == 202
    assert job["operation"] == "image.from_raw"
    assert job["options"]["format"] == "JPEG"
    assert "quality" not in job["options"]


def test_raw_api_rejects_empty_file_selection(settings):
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/jobs",
            data={"operation": "image.from_raw", "options": json.dumps({"format": "JPEG"})},
            files={"files": (None, "")},
        )
        with sqlite3.connect(settings.database_path) as connection:
            job_count = connection.execute("SELECT COUNT(*) FROM conversion_jobs").fetchone()[0]

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_options"
    assert job_count == 0


@pytest.mark.parametrize(
    "filename,options,status,error_code",
    [
        ("camera.jpg", {"format": "JPEG"}, 415, "unsupported_format"),
        ("camera.cr2", {"format": "PNG"}, 422, "invalid_options"),
        ("camera.cr2", {"format": "JPEG", "quality": 90}, 422, "invalid_options"),
    ],
)
def test_raw_api_rejects_unsupported_uploads_before_creating_job(
    settings, filename, options, status, error_code
):
    with TestClient(create_app(settings)) as client:
        response = _submit(client, [filename], options=options)
        with sqlite3.connect(settings.database_path) as connection:
            job_count = connection.execute("SELECT COUNT(*) FROM conversion_jobs").fetchone()[0]

    assert response.status_code == status
    assert response.json()["error"]["code"] == error_code
    assert job_count == 0


def test_raw_api_rejects_files_over_native_decoder_limit(settings, monkeypatch):
    monkeypatch.setattr(app_main, "MAX_RAW_INPUT_BYTES", 2)
    with TestClient(create_app(settings)) as client:
        response = _submit(client, ["large.cr2"])
        with sqlite3.connect(settings.database_path) as connection:
            job_count = connection.execute("SELECT COUNT(*) FROM conversion_jobs").fetchone()[0]

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"
    assert job_count == 0


def test_raw_api_and_worker_return_jpeg_or_zip_for_batches(settings, monkeypatch):
    from i_love_open_converter import worker

    def fake_convert(source, destination, image_format):
        assert image_format == "JPEG"
        destination.write_bytes(b"\xff\xd8\xffconverted")
        return "image/jpeg", destination.stat().st_size

    monkeypatch.setattr(worker, "convert_raw_to_jpeg", fake_convert)
    with TestClient(create_app(settings)) as client:
        single = _submit(client, ["single.cr2"])
        batch = _submit(client, ["one.cr2", "two.nef"])
        assert single.status_code == batch.status_code == 202
        assert process_one_job(settings)
        assert process_one_job(settings)
        single_download = client.get(single.json()["status_url"] + "/download")
        batch_download = client.get(batch.json()["status_url"] + "/download")

    assert single_download.status_code == 200
    assert single_download.headers["content-type"] == "image/jpeg"
    assert single_download.content.startswith(b"\xff\xd8\xff")
    assert batch_download.status_code == 200
    assert batch_download.headers["content-type"] == "application/zip"
    with ZipFile(BytesIO(batch_download.content)) as archive:
        assert archive.namelist() == ["one.jpg", "two.jpg"]
        assert all(archive.read(name).startswith(b"\xff\xd8\xff") for name in archive.namelist())


def test_raw_worker_removes_all_partial_batch_outputs_on_failure(settings, monkeypatch):
    from i_love_open_converter import worker

    conversions = 0

    def fail_on_second_file(source, destination, image_format):
        nonlocal conversions
        conversions += 1
        assert image_format == "JPEG"
        if conversions == 2:
            raise InvalidRawError
        destination.write_bytes(b"\xff\xd8\xffpartial")
        return "image/jpeg", destination.stat().st_size

    monkeypatch.setattr(worker, "convert_raw_to_jpeg", fail_on_second_file)
    with TestClient(create_app(settings)) as client:
        submitted = _submit(client, ["first.cr2", "second.nef"])
        assert submitted.status_code == 202
        assert process_one_job(settings)
        status = client.get(submitted.json()["status_url"])
        download = client.get(submitted.json()["status_url"] + "/download")

    output = settings.jobs_dir / submitted.json()["job_id"] / "output"
    assert status.json()["state"] == "failed"
    assert status.json()["error"]["code"] == "invalid_file"
    assert download.status_code == 409
    assert not output.exists()


def test_raw_catalog_and_form_are_available_in_both_languages(settings):
    with TestClient(create_app(settings)) as client:
        page = client.get("/").text
        script = client.get("/static/js/app.js").text

    assert 'data-tool="image.from_raw"' in page
    assert 'data-option="raw-note"' in page
    assert 'fromRawTitle: "Converter de RAW"' in script
    assert 'fromRawTitle: "Convert from RAW"' in script
    assert ".3fr" in script and ".srw" in script and ".x3f" not in script
    assert 'imageCount: "18 dispon\u00edveis"' in script
    assert 'imageCount: "18 available"' in script


def test_real_camera_raw_fixture_decodes_and_renders_a_bounded_image():
    rawpy = pytest.importorskip("rawpy")
    assert RAW_FIXTURE.is_file()
    with rawpy.imread(str(RAW_FIXTURE)) as raw:
        assert raw.sizes.width > 0
        assert raw.sizes.height > 0
        image = raw.postprocess(
            use_camera_wb=True,
            output_color=rawpy.ColorSpace.sRGB,
            output_bps=8,
            user_flip=None,
            no_auto_bright=False,
        )

    assert image.ndim == 3
    assert image.shape[2] == 3
    assert image.shape[0] * image.shape[1] <= raw_ops.MAX_RAW_PIXELS


def test_raw_child_applies_limits_and_writes_metadata_free_jpeg(monkeypatch, tmp_path):
    pytest.importorskip("resource")
    from i_love_open_converter import raw_worker

    root = tmp_path / "worker"
    root.mkdir()
    source = root / "input.raw"
    destination = root / "output.jpg"
    source.write_bytes(b"camera raw data")
    limits = []
    restrictions = []
    calls = []

    class FakeRaw:
        sizes = SimpleNamespace(
            raw_width=8,
            raw_height=6,
            width=8,
            height=6,
            iwidth=8,
            iheight=6,
        )

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def postprocess(self, **kwargs):
            calls.append(kwargs)
            return np.zeros((6, 8, 3), dtype=np.uint8)

    rawpy_stub = SimpleNamespace(
        ColorSpace=SimpleNamespace(sRGB="sRGB"),
        imread=lambda _path: FakeRaw(),
    )
    monkeypatch.setitem(sys.modules, "rawpy", rawpy_stub)
    monkeypatch.setattr(
        raw_worker.resource, "setrlimit", lambda kind, value: limits.append((kind, value))
    )
    monkeypatch.setattr(
        raw_worker, "restrict", lambda *args, **kwargs: restrictions.append((args, kwargs))
    )
    monkeypatch.chdir(tmp_path)

    status = raw_worker.main(root, source, destination)

    assert status == 0
    assert raw_worker.resource.RLIMIT_AS == limits[0][0]
    assert limits[0][1] == (raw_worker.MAX_ADDRESS_SPACE_BYTES,) * 2
    assert limits[1][1] == (120, 120)
    assert limits[2][1] == (raw_ops.MAX_RAW_OUTPUT_BYTES,) * 2
    assert restrictions[0][0] == (root.resolve(),)
    assert restrictions[0][1] == {"allow_app": True, "allow_tmp": False}
    assert calls[0] == {
        "use_camera_wb": True,
        "output_color": "sRGB",
        "output_bps": 8,
        "user_flip": None,
        "no_auto_bright": False,
    }
    with Image.open(destination) as converted:
        assert converted.format == "JPEG"
        assert converted.size == (8, 6)
        assert not converted.getexif()
        assert "icc_profile" not in converted.info
        assert "xmp" not in converted.info


def test_raw_child_rejects_oversized_dimensions_before_demosaic(monkeypatch, tmp_path):
    pytest.importorskip("resource")
    from i_love_open_converter import raw_worker

    root = tmp_path / "worker"
    root.mkdir()
    source = root / "input.raw"
    destination = root / "output.jpg"
    source.write_bytes(b"camera raw data")
    calls = []

    class FakeRaw:
        sizes = SimpleNamespace(
            raw_width=raw_ops.MAX_RAW_DIMENSION + 1,
            raw_height=2,
            width=raw_ops.MAX_RAW_DIMENSION + 1,
            height=2,
            iwidth=raw_ops.MAX_RAW_DIMENSION + 1,
            iheight=2,
        )

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def postprocess(self, **_kwargs):
            calls.append(True)
            raise AssertionError("oversized images must not be demosaiced")

    rawpy_stub = SimpleNamespace(
        ColorSpace=SimpleNamespace(sRGB="sRGB"), imread=lambda _path: FakeRaw()
    )
    monkeypatch.setitem(sys.modules, "rawpy", rawpy_stub)
    monkeypatch.setattr(raw_worker.resource, "setrlimit", lambda *_args: None)
    monkeypatch.setattr(raw_worker, "restrict", lambda *_args, **_kwargs: None)
    monkeypatch.chdir(tmp_path)

    status = raw_worker.main(root, source, destination)

    assert status == 3
    assert calls == []
    assert not destination.exists()
