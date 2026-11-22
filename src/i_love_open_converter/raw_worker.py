"""Decode one camera RAW file after constraining the Linux child process."""

from __future__ import annotations

import os
import resource
import sys
from pathlib import Path

from .office_sandbox import restrict
from .raw_ops import MAX_RAW_DIMENSION, MAX_RAW_INPUT_BYTES, MAX_RAW_OUTPUT_BYTES, MAX_RAW_PIXELS

MAX_ADDRESS_SPACE_BYTES = 3 * 1024 * 1024 * 1024


def _dimensions_are_supported(sizes: object) -> bool:
    dimensions = (
        (getattr(sizes, "raw_width", 0), getattr(sizes, "raw_height", 0)),
        (getattr(sizes, "width", 0), getattr(sizes, "height", 0)),
        (getattr(sizes, "iwidth", 0), getattr(sizes, "iheight", 0)),
    )
    return all(
        1 <= width <= MAX_RAW_DIMENSION
        and 1 <= height <= MAX_RAW_DIMENSION
        and width * height <= MAX_RAW_PIXELS
        for width, height in dimensions
    )


def _decoded_dimensions_are_supported(width: int, height: int) -> bool:
    return (
        1 <= width <= MAX_RAW_DIMENSION
        and 1 <= height <= MAX_RAW_DIMENSION
        and width * height <= MAX_RAW_PIXELS
    )


def main(root: Path, source: Path, destination: Path) -> int:
    root = root.resolve()
    source = source.resolve()
    destination = destination.resolve()
    if (
        not root.is_dir()
        or source.parent != root
        or destination.parent != root
        or not source.is_file()
        or not 0 < source.stat().st_size <= MAX_RAW_INPUT_BYTES
    ):
        return 4

    try:
        resource.setrlimit(resource.RLIMIT_AS, (MAX_ADDRESS_SPACE_BYTES, MAX_ADDRESS_SPACE_BYTES))
        resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
        resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_RAW_OUTPUT_BYTES, MAX_RAW_OUTPUT_BYTES))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        os.chdir(root)
        restrict(root, allow_app=True, allow_tmp=False)
    except (OSError, ValueError):
        return 77

    try:
        import rawpy
        from PIL import Image
    except ImportError:
        return 77

    try:
        raw = rawpy.imread(source.name)
    except Exception:
        return 4
    try:
        with raw:
            if not _dimensions_are_supported(raw.sizes):
                return 3
            rgb = raw.postprocess(
                use_camera_wb=True,
                output_color=rawpy.ColorSpace.sRGB,
                output_bps=8,
                user_flip=None,
                no_auto_bright=False,
            )
        if (
            getattr(rgb, "ndim", 0) != 3
            or rgb.shape[2] != 3
            or not _decoded_dimensions_are_supported(rgb.shape[1], rgb.shape[0])
        ):
            return 3
        Image.fromarray(rgb).save(
            destination.name,
            format="JPEG",
            quality=92,
            optimize=False,
            progressive=False,
        )
        if not 0 < destination.stat().st_size <= MAX_RAW_OUTPUT_BYTES:
            destination.unlink(missing_ok=True)
            return 2
    except Exception:
        destination.unlink(missing_ok=True)
        return 2
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(2)
    sys.exit(main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])))
