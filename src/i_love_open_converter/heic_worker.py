"""Inspect and decode one HEIF file under memory, CPU, file, and Landlock limits."""

from __future__ import annotations

import os
import re
import resource
import subprocess
import sys
from pathlib import Path

from .heic_ops import (
    MAX_HEIC_DIMENSION,
    MAX_HEIC_INPUT_BYTES,
    MAX_HEIC_OUTPUT_BYTES,
    MAX_HEIC_PIXELS,
)
from .office_sandbox import restrict

HEIF_INFO = "/usr/local/bin/heif-info"
HEIF_DEC = "/usr/local/bin/heif-dec"
MAX_ADDRESS_SPACE_BYTES = 3 * 1024 * 1024 * 1024
INFO_TIMEOUT_SECONDS = 30
DECODE_TIMEOUT_SECONDS = 90
MAX_INFO_OUTPUT_BYTES = 1024 * 1024
IMAGE_LINE = re.compile(r"^image: (\d+)x(\d+) \(id=\d+\)(, primary)?$")


def inspect_dimensions(source: Path) -> tuple[int, int] | None:
    info_path = Path("heif-info.txt")
    try:
        with info_path.open("xb") as output:
            previous_file_limit = resource.getrlimit(resource.RLIMIT_FSIZE)
            resource.setrlimit(
                resource.RLIMIT_FSIZE, (MAX_INFO_OUTPUT_BYTES, previous_file_limit[1])
            )
            try:
                result = subprocess.run(
                    [HEIF_INFO, str(source)],
                    stdin=subprocess.DEVNULL,
                    stdout=output,
                    stderr=subprocess.DEVNULL,
                    timeout=INFO_TIMEOUT_SECONDS,
                    check=False,
                )
            finally:
                resource.setrlimit(resource.RLIMIT_FSIZE, previous_file_limit)
        if result.returncode != 0 or info_path.stat().st_size > MAX_INFO_OUTPUT_BYTES:
            return None
        details = info_path.read_text(encoding="utf-8", errors="replace")
    except (OSError, subprocess.TimeoutExpired):
        return None
    finally:
        info_path.unlink(missing_ok=True)

    if "sequence time scale:" in details or "image sequence" in details:
        return None
    images = [
        IMAGE_LINE.fullmatch(line.strip())
        for line in details.splitlines()
        if line.startswith("image:")
    ]
    if len(images) != 1 or images[0] is None or images[0].group(3) is None:
        return None

    width, height = int(images[0].group(1)), int(images[0].group(2))
    if (
        not 1 <= width <= MAX_HEIC_DIMENSION
        or not 1 <= height <= MAX_HEIC_DIMENSION
        or width * height > MAX_HEIC_PIXELS
    ):
        return width, height
    return width, height


def main(root: Path, source: Path, destination: Path) -> int:
    root = root.resolve()
    source = source.resolve()
    destination = destination.resolve()
    if (
        not root.is_dir()
        or source.parent != root
        or destination.parent != root
        or not source.is_file()
        or source.stat().st_size > MAX_HEIC_INPUT_BYTES
    ):
        return 4

    try:
        resource.setrlimit(resource.RLIMIT_AS, (MAX_ADDRESS_SPACE_BYTES, MAX_ADDRESS_SPACE_BYTES))
        resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
        resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_HEIC_OUTPUT_BYTES, MAX_HEIC_OUTPUT_BYTES))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        os.chdir(root)
        restrict(root, allow_app=True, allow_tmp=False)
    except (OSError, ValueError):
        return 77

    source_path = Path(source.name)
    destination_path = Path(destination.name)
    dimensions = inspect_dimensions(source_path)
    if dimensions is None:
        return 4
    width, height = dimensions
    if (
        not 1 <= width <= MAX_HEIC_DIMENSION
        or not 1 <= height <= MAX_HEIC_DIMENSION
        or width * height > MAX_HEIC_PIXELS
    ):
        return 3

    try:
        result = subprocess.run(
            [
                HEIF_DEC,
                "--quiet",
                "--quality",
                "92",
                "--transparency-composition-mode",
                "white",
                "--codec-threads",
                "1",
                "--tile-threads",
                "1",
                "--output",
                str(destination_path),
                str(source_path),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=DECODE_TIMEOUT_SECONDS,
            check=False,
        )
        if result.returncode != 0 or not destination_path.is_file():
            destination_path.unlink(missing_ok=True)
            return 2
        if not 0 < destination_path.stat().st_size <= MAX_HEIC_OUTPUT_BYTES:
            destination_path.unlink(missing_ok=True)
            return 2
    except (OSError, subprocess.TimeoutExpired):
        destination_path.unlink(missing_ok=True)
        return 2
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(2)
    sys.exit(main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])))
