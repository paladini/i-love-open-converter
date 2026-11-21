from dataclasses import replace
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from xml.etree import ElementTree
from zipfile import ZipFile

import pymupdf
from fastapi.testclient import TestClient
from PIL import Image

from i_love_open_converter import excel_worker, pdf_ops
from i_love_open_converter.main import create_app
from i_love_open_converter.worker import process_one_job


def _run_worker(monkeypatch):
    monkeypatch.setattr(pdf_ops, "word_isolated", lambda: True)
    monkeypatch.setattr(excel_worker, "_limit_resources", lambda: None)

    def run(command, **_kwargs):
        try:
            excel_worker.main(Path(command[-2]), Path(command[-1]))
        except excel_worker.NoSpreadsheetDataError:
            return SimpleNamespace(returncode=3)
        except Exception:
            return SimpleNamespace(returncode=1)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(pdf_ops.subprocess, "run", run)


def _tabular_pdf():
    pdf = pymupdf.open()
    page = pdf.new_page(width=360, height=240)
    page.draw_rect(pymupdf.Rect(48, 96, 312, 168), width=1)
    page.draw_line((180, 96), (180, 168), width=1)
    page.draw_line((48, 132), (312, 132), width=1)
    for x, y, value in [
        (56, 120, "Code"), (188, 120, "Value"),
        (56, 156, "00123"), (188, 156, "=SUM(1,1)"),
    ]:
        page.insert_text((x, y), value)
    page.insert_text((48, 60), "Outside table: https://example.invalid/data")
    data = pdf.tobytes()
    pdf.close()
    return data


def _sheet_text(archive, name):
    root = ElementTree.fromstring(archive.read(name))
    return "".join(node.text or "" for node in root.iter() if node.tag.endswith("}t"))


def test_pdf_to_excel_extracts_tables_and_text_as_literal_strings(settings, monkeypatch):
    _run_worker(monkeypatch)
    with TestClient(create_app(settings)) as client:
        home = client.get("/")
        assert home.status_code == 200
        assert 'href="/tools/pdf-to-excel"' in home.text
        assert client.get("/tools/pdf-to-excel").status_code == 200
        response = client.post(
            "/api/jobs", data={"operation": "pdf.to_excel"},
            files={"files": ("table.pdf", _tabular_pdf(), "application/pdf")},
        )
        assert response.status_code == 202
        assert process_one_job(settings)
        download = client.get(response.json()["status_url"] + "/download")
        assert download.status_code == 200
        assert download.headers["content-type"].startswith(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    with ZipFile(BytesIO(download.content)) as archive:
        names = set(archive.namelist())
        assert "xl/workbook.xml" in names
        assert {"xl/worksheets/sheet1.xml", "xl/worksheets/sheet2.xml"} <= names
        table_text = _sheet_text(archive, "xl/worksheets/sheet1.xml")
        text_text = _sheet_text(archive, "xl/worksheets/sheet2.xml")
        assert all(value in table_text for value in ("Source page", "00123", "=SUM(1,1)"))
        assert "Outside table: https://example.invalid/data" in text_text
        for name in names:
            if name.endswith(".xml") and name.startswith("xl/worksheets/"):
                root = ElementTree.fromstring(archive.read(name))
                assert not any(node.tag.endswith("}f") for node in root.iter())
        assert not any("externalLinks" in name for name in names)


def test_pdf_to_excel_rejects_invalid_multiple_and_encrypted_pdfs(settings, pdf_bytes):
    with TestClient(create_app(settings)) as client:
        invalid = client.post(
            "/api/jobs", data={"operation": "pdf.to_excel"},
            files={"files": ("bad.pdf", b"invalid", "application/pdf")},
        )
        assert invalid.status_code == 422
        multiple = client.post(
            "/api/jobs", data={"operation": "pdf.to_excel"},
            files=[("files", ("a.pdf", pdf_bytes)), ("files", ("b.pdf", pdf_bytes))],
        )
        assert multiple.status_code == 422
        pdf = pymupdf.open()
        pdf.new_page()
        encrypted = pdf.tobytes(
            encryption=pymupdf.PDF_ENCRYPT_AES_256,
            owner_pw="owner-password", user_pw="user-password",
        )
        pdf.close()
        locked = client.post(
            "/api/jobs", data={"operation": "pdf.to_excel"},
            files={"files": ("locked.pdf", encrypted, "application/pdf")},
        )
        assert locked.status_code == 422


def test_scanned_image_without_text_fails_without_empty_workbook(settings, monkeypatch):
    _run_worker(monkeypatch)
    image = BytesIO()
    Image.new("RGB", (100, 80), "white").save(image, "PNG")
    pdf = pymupdf.open()
    pdf.new_page(width=240, height=160).insert_image(
        pymupdf.Rect(0, 0, 240, 160), stream=image.getvalue()
    )
    source = pdf.tobytes()
    pdf.close()
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/jobs", data={"operation": "pdf.to_excel"},
            files={"files": ("scan.pdf", source, "application/pdf")},
        )
        assert response.status_code == 202
        assert process_one_job(settings)
        status = client.get(response.json()["status_url"]).json()
        assert status["state"] == "failed"
        assert status["error"]["code"] == "no_extractable_data"
        assert client.get(response.json()["status_url"] + "/download").status_code != 200


def test_pdf_to_excel_requires_isolated_worker(settings, pdf_bytes, monkeypatch):
    monkeypatch.setattr(pdf_ops, "word_isolated", lambda: False)
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/jobs", data={"operation": "pdf.to_excel"},
            files={"files": ("input.pdf", pdf_bytes, "application/pdf")},
        )
        assert response.status_code == 202
        assert process_one_job(settings)
        status = client.get(response.json()["status_url"]).json()
        assert status["state"] == "failed" and status["error"]["code"] == "excel_unavailable"
        assert client.get(response.json()["status_url"] + "/download").status_code != 200


def test_excel_worker_rejects_more_than_two_hundred_pages(settings, tmp_path, monkeypatch):
    _run_worker(monkeypatch)
    settings = replace(settings, max_file_size_mb=5, max_total_upload_mb=6)
    pdf = pymupdf.open()
    for _ in range(201):
        pdf.new_page(width=240, height=120)
    source = tmp_path / "too-many-pages.pdf"
    pdf.save(source)
    pdf.close()
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/jobs", data={"operation": "pdf.to_excel"},
            files={"files": ("too-many-pages.pdf", source.read_bytes(), "application/pdf")},
        )
        assert response.status_code == 202
        assert process_one_job(settings)
        status = client.get(response.json()["status_url"]).json()
        assert status["state"] == "failed" and status["error"]["code"] == "excel_failed"
        assert client.get(response.json()["status_url"] + "/download").status_code != 200


def test_excel_worker_rejects_oversized_page_without_download(settings, tmp_path, monkeypatch):
    _run_worker(monkeypatch)
    pdf = pymupdf.open()
    pdf.new_page(width=5000, height=5000).insert_text((50, 50), "Too large")
    source = tmp_path / "oversized.pdf"
    pdf.save(source)
    pdf.close()
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/jobs", data={"operation": "pdf.to_excel"},
            files={"files": ("oversized.pdf", source.read_bytes(), "application/pdf")},
        )
        assert response.status_code == 202
        assert process_one_job(settings)
        status = client.get(response.json()["status_url"]).json()
        assert status["state"] == "failed" and status["error"]["code"] == "excel_failed"
        assert client.get(response.json()["status_url"] + "/download").status_code != 200


def test_excel_worker_enforces_table_cell_limit(settings, monkeypatch):
    _run_worker(monkeypatch)
    assert excel_worker.MAX_TABLE_CELLS == 200_000
    monkeypatch.setattr(excel_worker, "MAX_TABLE_CELLS", 1)
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/jobs", data={"operation": "pdf.to_excel"},
            files={"files": ("table.pdf", _tabular_pdf(), "application/pdf")},
        )
        assert response.status_code == 202
        assert process_one_job(settings)
        status = client.get(response.json()["status_url"]).json()
        assert status["state"] == "failed" and status["error"]["code"] == "excel_failed"
        assert client.get(response.json()["status_url"] + "/download").status_code != 200


def test_excel_worker_enforces_text_line_limit(settings, pdf_bytes, monkeypatch):
    _run_worker(monkeypatch)
    assert excel_worker.MAX_TEXT_LINES == 100_000
    monkeypatch.setattr(excel_worker, "MAX_TEXT_LINES", 1)
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/jobs", data={"operation": "pdf.to_excel"},
            files={"files": ("text.pdf", pdf_bytes, "application/pdf")},
        )
        assert response.status_code == 202
        assert process_one_job(settings)
        status = client.get(response.json()["status_url"]).json()
        assert status["state"] == "failed" and status["error"]["code"] == "excel_failed"
        assert client.get(response.json()["status_url"] + "/download").status_code != 200


def test_excel_timeout_fails_without_download(settings, pdf_bytes, monkeypatch):
    monkeypatch.setattr(pdf_ops, "word_isolated", lambda: True)

    def timeout(command, **_kwargs):
        raise pdf_ops.subprocess.TimeoutExpired(command, 180)

    monkeypatch.setattr(pdf_ops.subprocess, "run", timeout)
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/jobs", data={"operation": "pdf.to_excel"},
            files={"files": ("input.pdf", pdf_bytes, "application/pdf")},
        )
        assert response.status_code == 202
        assert process_one_job(settings)
        status = client.get(response.json()["status_url"]).json()
        assert status["state"] == "failed" and status["error"]["code"] == "excel_failed"
        assert client.get(response.json()["status_url"] + "/download").status_code != 200


def test_excel_output_limit_removes_partial_workbook(tmp_path, monkeypatch, pdf_bytes):
    monkeypatch.setattr(excel_worker, "_limit_resources", lambda: None)
    monkeypatch.setattr(excel_worker, "MAX_OUTPUT_BYTES", 1)
    source, destination = tmp_path / "input.pdf", tmp_path / "partial.xlsx"
    source.write_bytes(pdf_bytes)
    try:
        excel_worker.main(source, destination)
    except ValueError as exc:
        assert "output limit" in str(exc)
    else:
        raise AssertionError("output limit was not enforced")
    assert not destination.exists()
