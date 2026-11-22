"""Validate and convert PSD files in a bounded, filesystem-restricted child process."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

from .office_ops import office_isolated

MAX_PSD_PIXELS = 40_000_000
MAX_PSD_OUTPUT_BYTES = 256 * 1024 * 1024
PSD_TIMEOUT_SECONDS = 120
PSD_HEADER_BYTES = 26


class InvalidPsdError(Exception):
    """The file is not a supported PSD document."""


class PsdUnavailableError(Exception):
    """The required isolated Linux worker is unavailable."""


class PsdConversionError(Exception):
    """The PSD renderer failed or exceeded its resource bounds."""


def contains_smart_objects(document) -> bool:
    """Find smart-object layers without opening their embedded or linked contents."""
    stack = list(document)
    while stack:
        layer = stack.pop()
        if layer.kind == "smartobject":
            return True
        if layer.is_group():
            stack.extend(layer)
    return False


def inspect_psd(source: Path) -> tuple[int, int]:
    """Validate the fixed PSD header without allocating document pixel buffers."""
    try:
        if source.stat().st_size < PSD_HEADER_BYTES:
            raise InvalidPsdError
        with source.open("rb") as stream:
            header = stream.read(PSD_HEADER_BYTES)
    except OSError as exc:
        raise InvalidPsdError from exc
    if len(header) != PSD_HEADER_BYTES or header[:4] != b"8BPS" or header[4:6] != b"\x00\x01":
        raise InvalidPsdError
    if any(header[6:12]):
        raise InvalidPsdError
    channels = int.from_bytes(header[12:14], "big")
    height = int.from_bytes(header[14:18], "big")
    width = int.from_bytes(header[18:22], "big")
    depth = int.from_bytes(header[22:24], "big")
    color_mode = int.from_bytes(header[24:26], "big")
    expected_channels = 1 <= channels <= 2 if color_mode == 1 else 3 <= channels <= 4
    if (
        depth != 8
        or color_mode not in {1, 3}
        or not expected_channels
        or not 1 <= width <= 30_000
        or not 1 <= height <= 30_000
        or width * height > MAX_PSD_PIXELS
    ):
        raise InvalidPsdError
    return width, height


def convert_psd_to_image(
    source: Path, destination: Path, image_format: str, width: int, height: int
) -> tuple[str, int]:
    if image_format not in {"PNG", "JPEG", "WEBP"}:
        raise InvalidPsdError
    if not office_isolated():
        raise PsdUnavailableError
    if inspect_psd(source) != (width, height):
        raise InvalidPsdError

    suffix = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}[image_format]
    destination.unlink(missing_ok=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix="psd-render-") as temporary:
            root = Path(temporary).resolve()
            (root / "cache").mkdir()
            input_path = root / "input.psd"
            output_path = root / f"rendered{suffix}"
            shutil.copyfile(source, input_path)
            environment = {
                **os.environ,
                "HOME": str(root),
                "TMPDIR": str(root),
                "XDG_CACHE_HOME": str(root / "cache"),
                "PYTHONDONTWRITEBYTECODE": "1",
            }
            try:
                process = subprocess.Popen(
                    [sys.executable, "-m", "i_love_open_converter.psd_worker", str(root),
                     str(input_path), str(output_path), image_format],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                    env=environment,
                )
                try:
                    process.wait(timeout=PSD_TIMEOUT_SECONDS)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                    raise
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise PsdConversionError from exc
            if process.returncode == 77:
                raise PsdUnavailableError
            if process.returncode != 0 or not output_path.is_file():
                raise PsdConversionError
            output_size = output_path.stat().st_size
            if not 0 < output_size <= MAX_PSD_OUTPUT_BYTES:
                raise PsdConversionError
            shutil.copyfile(output_path, destination)
    except (OSError, shutil.Error) as exc:
        destination.unlink(missing_ok=True)
        raise PsdConversionError from exc
    mime = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}[image_format]
    return mime, destination.stat().st_size
