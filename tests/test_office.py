from __future__ import annotations

import subprocess
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pymupdf
import pytest
from fastapi.testclient import TestClient

from i_love_open_converter import office_ops
from i_love_open_converter.main import create_app
from i_love_open_converter.worker import process_one_job


@pytest.mark.parametrize(
    "family,ext", [("word", "docx"), ("powerpoint", "pptx"), ("excel", "xlsx")]
)
def test_office_job_and_download(settings, monkeypatch, family, ext):
    def fake_convert(source, output):
        assert source.read_bytes() == b"office input"
        output.mkdir(parents=True, exist_ok=True)
        destination = output / "converted.pdf"
        pdf = pymupdf.open()
        pdf.new_page().insert_text((40, 40), "converted")
        pdf.save(destination)
        pdf.close()
        return destination

    monkeypatch.setattr("i_love_open_converter.worker.convert_office", fake_convert)
    with TestClient(create_app(settings)) as client:
        assert client.get(f"/tools/office-to-pdf/{family}").status_code == 200
        response = client.post(
            "/api/jobs", data={"operation": f"office.{family}_to_pdf"},
            files={"files": (f"sample.{ext}", BytesIO(b"office input"),
                             "application/octet-stream")},
        )
        assert response.status_code == 202
        assert process_one_job(settings)
        result = client.get(response.json()["status_url"] + "/download")
        assert result.status_code == 200
        with pymupdf.open(stream=result.content, filetype="pdf") as document:
            assert "converted" in document[0].get_text()


def test_office_isolation_fails_closed(settings, monkeypatch):
    monkeypatch.setattr(office_ops.shutil, "which", lambda _: "/usr/bin/soffice")
    monkeypatch.setattr(office_ops, "office_isolated", lambda: False)
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/jobs", data={"operation": "office.word_to_pdf"},
            files={"files": ("sample.docx", b"input", "application/octet-stream")},
        )
        assert response.status_code == 202
        assert process_one_job(settings)
        status = client.get(response.json()["status_url"]).json()
        assert status["state"] == "failed"
        assert status["error"]["code"] == "office_unavailable"
        assert client.get(response.json()["status_url"] + "/download").status_code != 200


def test_office_rejects_wrong_extension_and_multiple_files(settings):
    with TestClient(create_app(settings)) as client:
        invalid = client.post(
            "/api/jobs", data={"operation": "office.word_to_pdf"},
            files={"files": ("sample.xlsx", b"input", "application/octet-stream")},
        )
        assert invalid.status_code == 415
        multiple = client.post(
            "/api/jobs", data={"operation": "office.word_to_pdf"},
            files=[("files", ("a.docx", b"a")), ("files", ("b.docx", b"b"))],
        )
        assert multiple.status_code == 422


def test_office_rejects_mismatched_and_invalid_container(tmp_path):
    source = tmp_path / "wrong.docx"
    with ZipFile(source, "w") as archive:
        archive.writestr("[Content_Types].xml", "types")
        archive.writestr("xl/workbook.xml", "spreadsheet")
    with pytest.raises(office_ops.OfficeConversionError):
        office_ops.validate_office(source)
    source.write_bytes(b"plain text masquerading as a Word document")
    with pytest.raises(office_ops.OfficeConversionError):
        office_ops.validate_office(source)


def test_office_rejects_excessive_uncompressed_package(tmp_path, monkeypatch):
    monkeypatch.setattr(office_ops, "MAX_PART_BYTES", 1024)
    source = tmp_path / "large.docx"
    with ZipFile(source, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "types")
        archive.writestr("word/document.xml", "x" * 2048)
    assert source.stat().st_size < 1024
    with pytest.raises(office_ops.OfficeConversionError):
        office_ops.validate_office(source)
    monkeypatch.setattr(office_ops, "MAX_PART_BYTES", 4096)
    monkeypatch.setattr(office_ops, "MAX_EXPANDED_BYTES", 1024)
    with pytest.raises(office_ops.OfficeConversionError):
        office_ops.validate_office(source)


def test_office_timeout_kills_the_process_group(tmp_path, monkeypatch):
    source = tmp_path / "valid.docx"
    with ZipFile(source, "w") as archive:
        archive.writestr("[Content_Types].xml", "types")
        archive.writestr("word/document.xml", "document")
    killed = []

    class SlowProcess:
        pid = 1234

        def __init__(self):
            self.calls = 0

        def wait(self, timeout=None):
            self.calls += 1
            if self.calls == 1:
                raise subprocess.TimeoutExpired("soffice", timeout)

    monkeypatch.setattr(office_ops, "office_isolated", lambda: True)
    monkeypatch.setattr(office_ops.shutil, "which", lambda _: "/usr/bin/soffice")
    monkeypatch.setattr(office_ops.subprocess, "Popen", lambda *a, **kw: SlowProcess())
    monkeypatch.setattr(
        office_ops.os, "killpg", lambda pid, sig: killed.append((pid, sig)), raising=False
    )
    monkeypatch.setattr(office_ops.signal, "SIGKILL", 9, raising=False)
    with pytest.raises(office_ops.OfficeConversionError):
        office_ops.convert_office(source, tmp_path / "out")
    assert killed == [(1234, office_ops.signal.SIGKILL)]
    assert not (tmp_path / "out" / "converted.pdf").exists()
