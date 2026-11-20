from __future__ import annotations

import ctypes
import os
import platform
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
from pathlib import Path
from zipfile import BadZipFile, ZipFile

import olefile
import pymupdf


class OfficeConversionError(Exception):
    """The Office document could not be safely converted."""


class OfficeUnavailableError(OfficeConversionError):
    """The converter or required network isolation is unavailable."""


FAMILIES = {
    "office.word_to_pdf": {".doc", ".docx"},
    "office.powerpoint_to_pdf": {".ppt", ".pptx"},
    "office.excel_to_pdf": {".xls", ".xlsx"},
}

PROFILE = '''<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry">
  <item oor:path="/org.openoffice.Office.Common/Security/Scripting">
    <prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop>
    <prop oor:name="SecureURL" oor:op="fuse"><value></value></prop>
  </item>
</oor:items>
'''

DOCUMENT_PARTS = {".docx": "word/document.xml", ".pptx": "ppt/presentation.xml",
                  ".xlsx": "xl/workbook.xml"}
LEGACY_PARTS = {".doc": {"WordDocument"}, ".ppt": {"PowerPoint Document"},
                ".xls": {"Workbook", "Book"}}
MAX_PART_BYTES = 64 * 1024 * 1024
MAX_EXPANDED_BYTES = 256 * 1024 * 1024


def validate_office(source: Path) -> None:
    """Reject mismatched and obviously invalid Office containers before conversion."""
    extension = source.suffix.lower()
    try:
        if extension in DOCUMENT_PARTS:
            with ZipFile(source) as archive:
                entries = archive.infolist()
                names = [item.filename for item in entries]
                if (len(entries) > 10000 or len(names) != len(set(names))
                        or any(item.flag_bits & 1 for item in entries)
                        or any(item.file_size > MAX_PART_BYTES for item in entries)
                        or sum(item.file_size for item in entries) > MAX_EXPANDED_BYTES
                        or "[Content_Types].xml" not in names
                        or DOCUMENT_PARTS[extension] not in names):
                    raise OfficeConversionError
        elif extension in LEGACY_PARTS:
            with olefile.OleFileIO(source) as archive:
                if not any(archive.exists(part) for part in LEGACY_PARTS[extension]):
                    raise OfficeConversionError
        else:
            raise OfficeConversionError
    except (OSError, ValueError, BadZipFile) as exc:
        raise OfficeConversionError from exc


def office_isolated() -> bool:
    """Require Linux and a network namespace without external interfaces."""
    if (sys.platform != "linux" or platform.machine().lower() not in {"x86_64", "aarch64"}
            or os.environ.get("OFFICE_NETWORK_ISOLATED") != "1"):
        return False
    try:
        if {name for _, name in socket.if_nameindex()} != {"lo"}:
            return False
        libc = ctypes.CDLL(None, use_errno=True)
        return libc.syscall(444, 0, 0, 1) >= 1
    except OSError:
        return False


def convert_office(source: Path, output_dir: Path) -> Path:
    binary = shutil.which("soffice")
    if binary is None or not office_isolated():
        raise OfficeUnavailableError
    validate_office(source)
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="office-conversion-") as temp:
        root = Path(temp)
        profile = root / "profile"
        (profile / "user").mkdir(parents=True)
        (profile / "user" / "registrymodifications.xcu").write_text(PROFILE, encoding="utf-8")
        input_path = root / ("input" + source.suffix.lower())
        shutil.copyfile(source, input_path)
        try:
            process = subprocess.Popen(
                [sys.executable, str(Path(__file__).with_name("office_sandbox.py")), str(root),
                 binary, f"-env:UserInstallation={profile.as_uri()}", "--headless", "--norestore",
                 "--convert-to", "pdf", "--outdir", str(root), str(input_path)],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True,
                env={**os.environ, "HOME": str(root), "XDG_CACHE_HOME": str(root / "cache"),
                     "TMPDIR": str(root)},
            )
            try:
                process.wait(timeout=120)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                raise
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise OfficeConversionError from exc
        converted = root / "input.pdf"
        if process.returncode == 77:
            raise OfficeUnavailableError
        if process.returncode != 0 or not converted.is_file():
            raise OfficeConversionError
        try:
            with pymupdf.open(converted) as pdf:
                if pdf.needs_pass or not pdf.is_pdf or pdf.page_count < 1:
                    raise OfficeConversionError
        except (RuntimeError, ValueError) as exc:
            raise OfficeConversionError from exc
        destination = output_dir / "converted.pdf"
        shutil.copyfile(converted, destination)
        return destination
