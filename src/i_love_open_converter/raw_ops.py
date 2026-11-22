"""Run camera RAW decoding in a per-file, resource-limited Linux child."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

from .office_ops import office_isolated

MAX_RAW_PIXELS = 40_000_000
MAX_RAW_DIMENSION = 32_768
MAX_RAW_INPUT_BYTES = 100 * 1024 * 1024
MAX_RAW_OUTPUT_BYTES = 256 * 1024 * 1024
RAW_TIMEOUT_SECONDS = 125
RAW_EXTENSIONS = frozenset(
    {
        ".3fr",
        ".ari",
        ".arw",
        ".bay",
        ".cap",
        ".cr2",
        ".cr3",
        ".crw",
        ".dcr",
        ".dcs",
        ".dng",
        ".drf",
        ".eip",
        ".erf",
        ".fff",
        ".gpr",
        ".iiq",
        ".k25",
        ".kdc",
        ".mdc",
        ".mef",
        ".mos",
        ".mrw",
        ".nef",
        ".nrw",
        ".orf",
        ".pef",
        ".ptx",
        ".raf",
        ".raw",
        ".rw2",
        ".rwl",
        ".sr2",
        ".srf",
        ".srw",
    }
)


class InvalidRawError(Exception):
    """The source is not a readable RAW image."""


class RawImageTooLargeError(Exception):
    """The decoded RAW image exceeds the supported dimensions."""


class RawUnavailableError(Exception):
    """The isolated Linux RAW decoder is unavailable."""


class RawConversionError(Exception):
    """The RAW decoder failed or exceeded its resource limits."""


def convert_raw_to_jpeg(source: Path, destination: Path, image_format: str) -> tuple[str, int]:
    if image_format != "JPEG" or source.suffix.lower() not in RAW_EXTENSIONS:
        raise InvalidRawError
    if not office_isolated():
        raise RawUnavailableError

    try:
        source_size = source.stat().st_size
    except OSError as exc:
        raise InvalidRawError from exc
    if not 0 < source_size <= MAX_RAW_INPUT_BYTES:
        raise InvalidRawError

    destination.unlink(missing_ok=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix="raw-render-") as temporary:
            root = Path(temporary).resolve()
            (root / "cache").mkdir()
            input_path = root / "input.raw"
            output_path = root / "rendered.jpg"
            shutil.copyfile(source, input_path)
            environment = {
                "HOME": str(root),
                "TMPDIR": str(root),
                "XDG_CACHE_HOME": str(root / "cache"),
                "PYTHONDONTWRITEBYTECODE": "1",
                "PATH": "/app/.venv/bin:/usr/local/bin:/usr/bin:/bin",
                "LANG": "C.UTF-8",
            }
            try:
                process = subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "i_love_open_converter.raw_worker",
                        str(root),
                        str(input_path),
                        str(output_path),
                    ],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                    env=environment,
                )
                try:
                    process.wait(timeout=RAW_TIMEOUT_SECONDS)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                    raise
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise RawConversionError from exc

            if process.returncode == 77:
                raise RawUnavailableError
            if process.returncode == 3:
                raise RawImageTooLargeError
            if process.returncode == 4:
                raise InvalidRawError
            if process.returncode != 0 or not output_path.is_file():
                raise RawConversionError
            output_size = output_path.stat().st_size
            if not 0 < output_size <= MAX_RAW_OUTPUT_BYTES:
                raise RawConversionError
            shutil.copyfile(output_path, destination)
    except RawUnavailableError:
        destination.unlink(missing_ok=True)
        raise
    except (OSError, shutil.Error) as exc:
        destination.unlink(missing_ok=True)
        raise RawConversionError from exc
    except (InvalidRawError, RawImageTooLargeError, RawConversionError):
        destination.unlink(missing_ok=True)
        raise

    return "image/jpeg", destination.stat().st_size
