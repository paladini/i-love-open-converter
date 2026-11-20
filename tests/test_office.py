from __future__ import annotations

from io import BytesIO
from zipfile import ZipFile

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
