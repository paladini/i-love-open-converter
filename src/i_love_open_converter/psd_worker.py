"""Render one untrusted PSD under memory, CPU, file and Landlock limits."""

from __future__ import annotations

import resource
import sys
from pathlib import Path

from .office_sandbox import restrict
from .psd_ops import contains_smart_objects

MAX_OUTPUT_BYTES = 256 * 1024 * 1024
MAX_ALLOCATION_BYTES = 512 * 1024 * 1024
MAX_ADDRESS_SPACE_BYTES = 3 * 1024 * 1024 * 1024
COMPOSITE_TILE_SIZE = 4096


def composite_in_bounded_tiles(psd, image_module, *, tile_size=COMPOSITE_TILE_SIZE):
    """Composite fixed-size viewports so psd-tools never packs a full canvas alpha plane."""
    if not 1 <= tile_size <= COMPOSITE_TILE_SIZE:
        raise ValueError("Invalid PSD composite tile size")
    left, top, right, bottom = psd.viewbox
    output = None
    try:
        for y in range(top, bottom, tile_size):
            for x in range(left, right, tile_size):
                tile_right = min(x + tile_size, right)
                tile_bottom = min(y + tile_size, bottom)
                tile = psd.composite(
                    viewport=(x, y, tile_right, tile_bottom),
                    color=1.0,
                    alpha=0.0,
                    ignore_preview=True,
                )
                if tile is None or tile.size != (tile_right - x, tile_bottom - y):
                    raise ValueError("PSD renderer returned an invalid viewport")
                try:
                    if output is None:
                        output = image_module.new(tile.mode, psd.size)
                    elif tile.mode != output.mode:
                        raise ValueError("PSD renderer changed color mode between viewports")
                    output.paste(tile, (x - left, y - top))
                finally:
                    tile.close()
        if output is None:
            raise ValueError("PSD renderer returned no pixels")
        return output
    except Exception:
        if output is not None:
            output.close()
        raise


def composite_document(psd, image_module):
    """Use bounded merged-data decoding for layerless files and tiles otherwise."""
    if len(psd) == 0:
        image = psd.topil()
        if image is not None:
            return image
    return composite_in_bounded_tiles(psd, image_module)


def main(root: Path, source: Path, destination: Path, image_format: str) -> int:
    try:
        resource.setrlimit(
            resource.RLIMIT_AS,
            (MAX_ADDRESS_SPACE_BYTES, MAX_ADDRESS_SPACE_BYTES),
        )
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
        image = composite_document(psd, Image)
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
