from __future__ import annotations

import shutil
import subprocess

import pymupdf
import pytest
from fastapi.testclient import TestClient

from i_love_open_converter.main import create_app
from i_love_open_converter.pdf_archive import PdfArchiveError, convert_pdfa
from i_love_open_converter.worker import process_one_job


@pytest.mark.parametrize(
    "outcome",
    [
        "valid",
        "noncompliant",
        "invalid_report",
        "changed_text",
        "converter_error",
        "validator_error",
    ],
)
def test_archive_requires_conversion_preserved_text_and_independent_validation(
    tmp_path, monkeypatch, pdf_bytes, outcome
):
    source = tmp_path / "input.pdf"
    source.write_bytes(pdf_bytes)
    destination = tmp_path / "output.pdf"
    definition = tmp_path / "PDFA_def.ps"
    definition.write_text("% (srgb.icc) comment\n/ICCProfile (srgb.icc) def\n")
    profile = tmp_path / "srgb.icc"
    profile.write_bytes(b"test profile")
    monkeypatch.setenv("GS_PDFA_DEFINITION", str(definition))
    monkeypatch.setenv("GS_ICC_PROFILE", str(profile))
    monkeypatch.setenv("GS_BIN", "test-gs")
    monkeypatch.setenv("VERAPDF_BIN", "test-verapdf")

    def run(arguments, *, check, timeout, stdout, stderr):
        assert check and timeout == 300 and stderr == subprocess.DEVNULL
        if arguments[0] == "test-gs":
            assert "-dPDFSTOPONERROR" in arguments and "-dPDFACompatibilityPolicy=2" in arguments
            if outcome == "converter_error":
                raise subprocess.CalledProcessError(1, arguments)
            if outcome == "changed_text":
                with pymupdf.open() as document:
                    document.new_page()
                    document.save(destination)
            else:
                shutil.copyfile(source, destination)
        else:
            assert arguments[0:3] == ["test-verapdf", "-f", "2b"]
            if outcome == "invalid_report":
                stdout.write(b"not XML")
            else:
                compliant = "false" if outcome == "noncompliant" else "true"
                failed = "1" if outcome == "validator_error" else "0"
                stdout.write(
                    (
                        f'<report><jobs><job><validationReport isCompliant="{compliant}" '
                        'jobEndStatus="normal" profileName="PDF/A-2b validation profile"/>'
                        f'</job></jobs><batchSummary totalJobs="1" failedToParse="{failed}" '
                        'encrypted="0" outOfMemory="0" veraExceptions="0"><validationReports '
                        'compliant="1" failedJobs="0"/>'
                        "</batchSummary></report>"
                    ).encode()
                )

    monkeypatch.setattr("i_love_open_converter.pdf_archive.subprocess.run", run)
    if outcome == "valid":
        convert_pdfa(source, destination)
        assert destination.read_bytes() == pdf_bytes
    else:
        with pytest.raises(PdfArchiveError):
            convert_pdfa(source, destination)


def test_pdfa_is_unavailable_without_installed_dependencies(settings, monkeypatch, pdf_bytes):
    monkeypatch.setattr("i_love_open_converter.main.pdfa_available", lambda: False)
    with TestClient(create_app(settings)) as client:
        assert client.get("/tools/pdf-pdfa").status_code == 503
        response = client.post(
            "/api/jobs",
            data={"operation": "pdf.pdfa"},
            files={"files": ("a.pdf", pdf_bytes, "application/pdf")},
        )
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "service_unavailable"


def test_pdfa_validation_failure_marks_job_failed_and_removes_output(
    settings, monkeypatch, pdf_bytes
):
    monkeypatch.setattr("i_love_open_converter.main.pdfa_available", lambda: True)

    def fail_conversion(source, destination):
        destination.write_bytes(b"invalid partial output")
        raise PdfArchiveError

    monkeypatch.setattr("i_love_open_converter.pdf_ops.convert_pdfa", fail_conversion)
    with TestClient(create_app(settings)) as client:
        submitted = client.post(
            "/api/jobs",
            data={"operation": "pdf.pdfa"},
            files={"files": ("a.pdf", pdf_bytes, "application/pdf")},
        )
        assert submitted.status_code == 202
        assert process_one_job(settings)
        status = client.get(submitted.json()["status_url"]).json()
        assert status["state"] == "failed"
        assert client.get(submitted.json()["status_url"] + "/download").status_code == 409
        assert not (settings.jobs_dir / submitted.json()["job_id"] / "output").exists()
