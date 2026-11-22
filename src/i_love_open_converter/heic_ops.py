"""Validate HEIF headers and convert images in a resource-limited Linux child."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

from .office_ops import office_isolated

MAX_HEIC_PIXELS = 40_000_000
MAX_HEIC_DIMENSION = 32_768
MAX_HEIC_INPUT_BYTES = 100 * 1024 * 1024
MAX_HEIC_OUTPUT_BYTES = 256 * 1024 * 1024
HEIC_TIMEOUT_SECONDS = 125
MAX_FTYP_BYTES = 4096
SUPPORTED_HEIF_BRANDS = {
    b"heic",
    b"heif",
    b"heix",
    b"hevc",
    b"hevx",
    b"heim",
    b"heis",
    b"hevm",
    b"hevs",
    b"mif1",
    b"mif2",
    b"msf1",
    b"msf2",
}


class InvalidHeicError(Exception):
    """The upload is not a supported HEIF file."""


class HeicImageTooLargeError(Exception):
    """The decoded still image is outside the supported dimension limits."""


class HeicUnavailableError(Exception):
    """The isolated Linux decoder is unavailable."""


class HeicConversionError(Exception):
    """The isolated HEIF decoder failed or exceeded its resource limits."""


def inspect_heic_header(source: Path) -> None:
    """Check a bounded ISO-BMFF file-type box without invoking a native parser."""
    try:
        size = source.stat().st_size
        if size < 16 or size > MAX_HEIC_INPUT_BYTES:
            raise InvalidHeicError
        with source.open("rb") as stream:
            header = stream.read(MAX_FTYP_BYTES)
    except OSError as exc:
        raise InvalidHeicError from exc

    box_size = int.from_bytes(header[:4], "big")
    if (
        len(header) < 16
        or header[4:8] != b"ftyp"
        or box_size < 16
        or box_size > MAX_FTYP_BYTES
        or box_size > size
        or (box_size - 16) % 4
    ):
        raise InvalidHeicError

    file_type = header[8:box_size]
    compatible = (file_type[index : index + 4] for index in range(8, len(file_type), 4))
    brands = {file_type[:4], *compatible}
    if not brands.intersection(SUPPORTED_HEIF_BRANDS):
        raise InvalidHeicError


def convert_heic_to_image(
    source: Path,
    destination: Path,
    image_format: str,
) -> tuple[str, int]:
    if image_format != "JPEG":
        raise InvalidHeicError
    if not office_isolated():
        raise HeicUnavailableError
    inspect_heic_header(source)
    destination.unlink(missing_ok=True)
    destination.parent.mkdir(parents=True, exist_ok=True)

    try:
        with tempfile.TemporaryDirectory(prefix="heic-render-") as temporary:
            root = Path(temporary).resolve()
            (root / "cache").mkdir()
            input_path = root / "input.heic"
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
                        "i_love_open_converter.heic_worker",
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
                    process.wait(timeout=HEIC_TIMEOUT_SECONDS)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                    raise
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise HeicConversionError from exc

            if process.returncode == 77:
                raise HeicUnavailableError
            if process.returncode == 3:
                raise HeicImageTooLargeError
            if process.returncode == 4:
                raise InvalidHeicError
            if process.returncode != 0 or not output_path.is_file():
                raise HeicConversionError
            output_size = output_path.stat().st_size
            if not 0 < output_size <= MAX_HEIC_OUTPUT_BYTES:
                raise HeicConversionError
            shutil.copyfile(output_path, destination)
    except HeicUnavailableError:
        destination.unlink(missing_ok=True)
        raise
    except (OSError, shutil.Error) as exc:
        destination.unlink(missing_ok=True)
        raise HeicConversionError from exc

    return "image/jpeg", destination.stat().st_size
