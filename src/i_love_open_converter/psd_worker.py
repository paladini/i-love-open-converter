"""Render one untrusted PSD under memory, CPU, file and Landlock limits."""

from __future__ import annotations

import resource
import sys
from pathlib import Path

from .office_sandbox import restrict
from .psd_ops import contains_smart_objects

MAX_OUTPUT_BYTES = 256 * 1024 * 1024
MAX_ALLOCATION_BYTES = 512 * 1024 * 1024


def main(root: Path, source: Path, destination: Path, image_format: str) -> int:
    try:
        resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
        resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
        resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_OUTPUT_BYTES, MAX_OUTPUT_BYTES))
        restrict(root, allow_app=True)
    except (OSError, ValueError):
        return 77

    from PIL import Image
    from psd_tools import ParseLimits, PSDImage

    try:
        psd = PSDImage.open(
            source,
            max_alloc_bytes=MAX_ALLOCATION_BYTES,
            parse_limits=ParseLimits(
                max_read_bytes=128 * 1024**2,
                max_total_bytes=512 * 1024**2,
                max_objects=100_000,
                max_nesting_depth=32,
            ),
        )
        if contains_smart_objects(psd):
            return 2
        image = psd.composite(color=1.0, alpha=0.0, ignore_preview=True)
        if image is None or image.size != psd.size or image.width * image.height > 40_000_000:
            return 2
        if image.mode not in {"RGB", "RGBA", "L", "LA"}:
            return 2
        destination.parent.mkdir(parents=True, exist_ok=True)
        if image_format == "JPEG":
            rgba = image.convert("RGBA")
            flattened = Image.new("RGB", rgba.size, "white")
            flattened.paste(rgba, mask=rgba.getchannel("A"))
            flattened.save(destination, format="JPEG", quality=92, optimize=True)
            flattened.close()
            rgba.close()
        elif image_format == "WEBP":
            image.save(destination, format="WEBP", quality=90, method=4)
        elif image_format == "PNG":
            image.save(destination, format="PNG", optimize=False)
        else:
            return 2
        image.close()
        if not 0 < destination.stat().st_size <= MAX_OUTPUT_BYTES:
            destination.unlink(missing_ok=True)
            return 2
        return 0
    except (OSError, ValueError, RuntimeError, MemoryError):
        destination.unlink(missing_ok=True)
        return 2


if __name__ == "__main__":
    if len(sys.argv) != 5:
        sys.exit(2)
    sys.exit(main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]))
