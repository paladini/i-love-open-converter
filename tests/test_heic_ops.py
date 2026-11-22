from __future__ import annotations

import json
import sqlite3
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient

from i_love_open_converter import heic_ops
from i_love_open_converter.database import get_job
from i_love_open_converter.heic_ops import (
    HeicConversionError,
    HeicImageTooLargeError,
    HeicUnavailableError,
    InvalidHeicError,
    convert_heic_to_image,
    inspect_heic_header,
)
from i_love_open_converter.main import create_app
from i_love_open_converter.worker import process_one_job


def _ftyp(major: bytes = b"heic", compatible: tuple[bytes, ...] = ()) -> bytes:
    payload = major + bytes(4) + b"".join(compatible)
    return (8 + len(payload)).to_bytes(4, "big") + b"ftyp" + payload


@pytest.mark.parametrize(
    "brand",
    [b"heic", b"heif", b"heix", b"hevc", b"mif1", b"msf1"],
)
def test_inspect_heic_header_accepts_supported_major_brands(tmp_path, brand):
    source = tmp_path / "photo.heic"
    source.write_bytes(_ftyp(brand))

    inspect_heic_header(source)


def test_inspect_heic_header_accepts_supported_compatible_brand(tmp_path):
    source = tmp_path / "photo.heif"
    source.write_bytes(_ftyp(b"zzzz", (b"mif1",)))

    inspect_heic_header(source)


@pytest.mark.parametrize(
    "content",
    [
        b"not a HEIF file",
        _ftyp(b"avif"),
        (100).to_bytes(4, "big") + b"ftypheic" + bytes(8),
        (17).to_bytes(4, "big") + b"ftypheic" + bytes(5),
        (16).to_bytes(4, "big") + b"freeheic" + bytes(4),
    ],
)
def test_inspect_heic_header_rejects_invalid_or_unsupported_ftyp(tmp_path, content):
    source = tmp_path / "invalid.heic"
    source.write_bytes(content)

    with pytest.raises(InvalidHeicError):
        inspect_heic_header(source)


def test_inspect_heic_header_rejects_files_over_the_native_decoder_limit(tmp_path):
    source = tmp_path / "oversized.heic"
    with source.open("wb") as output:
        output.truncate(heic_ops.MAX_HEIC_INPUT_BYTES + 1)

    with pytest.raises(InvalidHeicError):
        inspect_heic_header(source)


class _FakeProcess:
    def __init__(self, command, returncode=0):
        self.command = command
        self.returncode = returncode

    def wait(self, timeout):
        output_path = self.command[-1]
        if self.returncode == 0:
            from pathlib import Path

            Path(output_path).write_bytes(b"\xff\xd8\xffjpeg")


def test_convert_heic_launches_isolated_worker_and_returns_one_jpeg(tmp_path, monkeypatch):
    source = tmp_path / "photo.heic"
    source.write_bytes(_ftyp())
    destination = tmp_path / "output.jpg"
    calls = []

    def fake_popen(command, **kwargs):
        calls.append((command, kwargs))
        return _FakeProcess(command)

    monkeypatch.setattr(heic_ops, "office_isolated", lambda: True)
    monkeypatch.setattr(heic_ops.subprocess, "Popen", fake_popen)

    content_type, size = convert_heic_to_image(source, destination, "JPEG")

    command, options = calls[0]
    assert content_type == "image/jpeg"
    assert size == destination.stat().st_size
    assert destination.read_bytes().startswith(b"\xff\xd8\xff")
    assert "i_love_open_converter.heic_worker" in command
    assert options["start_new_session"] is True
    assert options["stdin"] is heic_ops.subprocess.DEVNULL
    assert options["stdout"] is heic_ops.subprocess.DEVNULL
    assert options["stderr"] is heic_ops.subprocess.DEVNULL
    assert options["env"]["HOME"] == command[-3]


@pytest.mark.parametrize(
    "returncode,error",
    [
        (2, HeicConversionError),
        (3, HeicImageTooLargeError),
        (4, InvalidHeicError),
        (77, HeicUnavailableError),
    ],
)
def test_convert_heic_maps_child_failures_and_removes_partial_output(
    tmp_path, monkeypatch, returncode, error
):
    source = tmp_path / "photo.heic"
    source.write_bytes(_ftyp())
    destination = tmp_path / "output.jpg"
    destination.write_bytes(b"old output")

    monkeypatch.setattr(heic_ops, "office_isolated", lambda: True)
    monkeypatch.setattr(
        heic_ops.subprocess,
        "Popen",
        lambda command, **kwargs: _FakeProcess(command, returncode),
    )

    with pytest.raises(error):
        convert_heic_to_image(source, destination, "JPEG")
    assert not destination.exists()


def test_convert_heic_fails_closed_without_worker_isolation(tmp_path, monkeypatch):
    source = tmp_path / "photo.heic"
    source.write_bytes(_ftyp())
    destination = tmp_path / "output.jpg"
    monkeypatch.setattr(heic_ops, "office_isolated", lambda: False)

    with pytest.raises(HeicUnavailableError):
        convert_heic_to_image(source, destination, "JPEG")

    assert not destination.exists()


def _submit(client, filenames, *, options=None):
    files = [("files", (filename, _ftyp(), "image/heic")) for filename in filenames]
    return client.post(
        "/api/jobs",
        data={"operation": "image.from_heic", "options": json.dumps(options or {"format": "JPEG"})},
        files=files,
    )


@pytest.mark.parametrize("extension", ["heic", "heif", "hif"])
def test_heic_api_queues_supported_extensions_with_jpeg_output(settings, extension):
    with TestClient(create_app(settings)) as client:
        response = _submit(client, [f"photo.{extension}"])

    assert response.status_code == 202


def test_heic_api_defaults_to_jpeg(settings):
    with TestClient(create_app(settings)) as client:
        response = _submit(client, ["photo.heic"], options={})
        job = get_job(settings.database_path, response.json()["job_id"])

    assert response.status_code == 202
    assert job["operation"] == "image.from_heic"
    assert job["options"]["format"] == "JPEG"
    assert "quality" not in job["options"]


@pytest.mark.parametrize(
    "filename,content,options,status,error_code",
    [
        ("photo.jpg", _ftyp(), {"format": "JPEG"}, 415, "unsupported_format"),
        ("photo.heic", _ftyp(b"avif"), {"format": "JPEG"}, 422, "invalid_file"),
        ("photo.heic", _ftyp(), {"format": "PNG"}, 422, "invalid_options"),
        ("photo.heic", _ftyp(), {"format": "JPEG", "quality": 90}, 422, "invalid_options"),
    ],
)
def test_heic_api_rejects_unsupported_uploads_before_creating_job(
    settings, filename, content, options, status, error_code
):
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/jobs",
            data={"operation": "image.from_heic", "options": json.dumps(options)},
            files={"files": (filename, content, "image/heic")},
        )
        with sqlite3.connect(settings.database_path) as connection:
            job_count = connection.execute("SELECT COUNT(*) FROM conversion_jobs").fetchone()[0]

    assert response.status_code == status
    assert response.json()["error"]["code"] == error_code
    assert job_count == 0


def test_heic_api_and_worker_return_one_jpeg_or_a_zip_for_batches(settings, monkeypatch):
    from i_love_open_converter import worker

    def fake_convert(source, destination, image_format):
        assert image_format == "JPEG"
        destination.write_bytes(b"\xff\xd8\xffconverted")
        return "image/jpeg", destination.stat().st_size

    monkeypatch.setattr(worker, "convert_heic_to_image", fake_convert)
    with TestClient(create_app(settings)) as client:
        single = _submit(client, ["single.heic"])
        batch = _submit(client, ["one.heic", "two.heif"])
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


def test_heic_catalog_and_form_are_available_in_both_languages(settings):
    with TestClient(create_app(settings)) as client:
        page = client.get("/").text
        script = client.get("/static/js/app.js").text

    assert 'data-tool="image.from_heic"' in page
    assert 'data-option="heic-note"' in page
    assert 'fromHeicTitle: "Converter de HEIC"' in script
    assert 'fromHeicTitle: "Convert from HEIC"' in script
    assert 'imageCount: "17 disponíveis"' in script
    assert 'imageCount: "17 available"' in script


def _run_heic_child(monkeypatch, tmp_path, image_info):
    resource = pytest.importorskip("resource")
    from i_love_open_converter import heic_worker

    root = tmp_path / "worker"
    root.mkdir()
    source = root / "input.heic"
    destination = root / "output.jpg"
    source.write_bytes(_ftyp())
    run_calls = []
    limits = []

    def fake_run(command, **kwargs):
        run_calls.append(command)
        if command[0] == heic_worker.HEIF_INFO:
            kwargs["stdout"].write(image_info.encode())
            return SimpleNamespace(returncode=0)
        output_path = Path(command[command.index("--output") + 1])
        output_path.write_bytes(b"\xff\xd8\xffdecoded")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(heic_worker.resource, "getrlimit", lambda kind: (256 * 1024**2,) * 2)
    monkeypatch.setattr(heic_worker.resource, "setrlimit", lambda kind, value: limits.append(value))
    monkeypatch.setattr(heic_worker, "restrict", lambda path, **kwargs: None)
    monkeypatch.setattr(heic_worker.subprocess, "run", fake_run)

    status = heic_worker.main(root, source, destination)
    return status, destination, run_calls, limits, resource, heic_worker


def test_heic_child_caps_info_output_and_decodes_a_single_primary_image(monkeypatch, tmp_path):
    status, destination, calls, limits, _, heic_worker = _run_heic_child(
        monkeypatch, tmp_path, "image: 640x480 (id=42), primary\n"
    )

    assert status == 0
    assert destination.read_bytes().startswith(b"\xff\xd8\xff")
    assert len(calls) == 2
    assert calls[1][calls[1].index("--quality") + 1] == "92"
    assert calls[1][calls[1].index("--transparency-composition-mode") + 1] == "white"
    assert "--with-exif" not in calls[1]
    assert "--with-xmp" not in calls[1]
    assert limits[-2] == (heic_worker.MAX_INFO_OUTPUT_BYTES, 256 * 1024**2)
    assert limits[-1] == (256 * 1024**2, 256 * 1024**2)
    assert limits[0] == (heic_worker.MAX_ADDRESS_SPACE_BYTES, heic_worker.MAX_ADDRESS_SPACE_BYTES)
    assert limits[1] == (120, 120)


@pytest.mark.parametrize(
    "details,expected",
    [
        ("image: 40x20 (id=1), primary\nimage: 40x20 (id=2)\n", 4),
        ("image: 32769x1 (id=1), primary\n", 3),
        ("image sequence\nsequence time scale: 30 Hz\n", 4),
    ],
)
def test_heic_child_rejects_extra_images_sequences_and_oversized_dimensions(
    monkeypatch, tmp_path, details, expected
):
    status, destination, calls, *_ = _run_heic_child(monkeypatch, tmp_path, details)

    assert status == expected
    assert not destination.exists()
    assert len(calls) == 1
