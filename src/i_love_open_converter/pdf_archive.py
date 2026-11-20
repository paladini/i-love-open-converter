from __future__ import annotations

import glob
import os
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pymupdf


class PdfArchiveError(Exception):
    """Conversion or independent PDF/A validation failed."""


def _paths() -> tuple[str, str, str, Path]:
    definition = os.getenv("GS_PDFA_DEFINITION")
    if not definition:
        candidates = sorted(glob.glob("/usr/share/ghostscript/*/lib/PDFA_def.ps"))
        definition = candidates[-1] if candidates else ""
    return (
        os.getenv("GS_BIN", "gs"),
        os.getenv("VERAPDF_BIN", "verapdf"),
        definition,
        Path(os.getenv("GS_ICC_PROFILE", "/usr/share/color/icc/ghostscript/srgb.icc")),
    )


def pdfa_available() -> bool:
    gs, validator, definition, profile = _paths()
    return bool(
        shutil.which(gs)
        and shutil.which(validator)
        and Path(definition).is_file()
        and profile.is_file()
    )


def _text_by_page(path: Path) -> list[str]:
    with pymupdf.open(path) as document:
        return [re.sub(r"\s+", "", page.get_text()) for page in document]


def convert_pdfa(source: Path, destination: Path) -> None:
    gs, validator, definition, profile = _paths()
    try:
        source_text = _text_by_page(source)
        template = Path(definition).read_text(encoding="utf-8")
        if (
            len(re.findall(r"^/ICCProfile\s+\(srgb\.icc\)", template, re.MULTILINE)) != 1
            or not profile.is_file()
        ):
            raise PdfArchiveError
        escaped_profile = (
            str(profile.resolve()).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        )
        template = re.sub(
            r"^/ICCProfile\s+\(srgb\.icc\)",
            lambda _: f"/ICCProfile ({escaped_profile})",
            template,
            count=1,
            flags=re.MULTILINE,
        )
        with tempfile.TemporaryDirectory(dir=destination.parent) as temp:
            prefix = Path(temp) / "pdfa.ps"
            prefix.write_text(template, encoding="utf-8")
            subprocess.run(
                [
                    gs,
                    "-dSAFER",
                    "-dPDFSTOPONERROR",
                    "-dPDFA=2",
                    "-dBATCH",
                    "-dNOPAUSE",
                    "-dPDFACompatibilityPolicy=2",
                    "-sColorConversionStrategy=RGB",
                    "-sDEVICE=pdfwrite",
                    f"--permit-file-read={profile.resolve()}",
                    f"-sOutputFile={destination.resolve()}",
                    str(prefix.resolve()),
                    str(source.resolve()),
                ],
                check=True,
                timeout=300,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if _text_by_page(destination) != source_text:
                raise PdfArchiveError
            with tempfile.TemporaryFile() as report:
                subprocess.run(
                    [
                        validator,
                        "-f",
                        "2b",
                        "--maxfailuresdisplayed",
                        "1",
                        str(destination.resolve()),
                    ],
                    check=True,
                    timeout=300,
                    stdout=report,
                    stderr=subprocess.DEVNULL,
                )
                if report.tell() > 4 * 1024 * 1024:
                    raise PdfArchiveError
                report.seek(0)
                root = ET.parse(report).getroot()
            reports = root.findall("./jobs/job/validationReport")
            batch = root.find("./batchSummary")
            summary = root.find("./batchSummary/validationReports")
            if (
                len(reports) != 1
                or reports[0].get("isCompliant") != "true"
                or reports[0].get("jobEndStatus") != "normal"
                or "PDF/A-2b" not in reports[0].get("profileName", "")
                or batch is None
                or batch.get("totalJobs") != "1"
                or any(
                    batch.get(key) != "0"
                    for key in ("failedToParse", "encrypted", "outOfMemory", "veraExceptions")
                )
                or summary is None
                or summary.get("compliant") != "1"
                or summary.get("failedJobs") != "0"
            ):
                raise PdfArchiveError
    except PdfArchiveError:
        raise
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, ET.ParseError) as exc:
        raise PdfArchiveError from exc
