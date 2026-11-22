"""Exercise static SVG rasterization in the isolated Linux worker runtime."""

from __future__ import annotations

import tempfile
from pathlib import Path

from PIL import Image

from i_love_open_converter.svg_ops import convert_svg_to_image, inspect_svg

SVG = b"""<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"64\" height=\"32\">
<rect x=\"0\" y=\"0\" width=\"32\" height=\"32\" fill=\"#ff0000\"/>
</svg>"""


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="svg-smoke-") as directory:
        root = Path(directory)
        source = root / "source.svg"
        source.write_bytes(SVG)
        assert inspect_svg(source) == (64, 32)
        for image_format, suffix in (("PNG", ".png"), ("JPEG", ".jpg"), ("WEBP", ".webp")):
            destination = root / f"result{suffix}"
            mime, size = convert_svg_to_image(source, destination, image_format, 64, 32)
            assert destination.is_file() and 0 < size == destination.stat().st_size
            assert mime == {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}[
                image_format
            ]
            with Image.open(destination) as image:
                assert image.size == (64, 32)
                assert image.format == image_format
                if image_format in {"PNG", "WEBP"}:
                    assert image.mode == "RGBA"
                    assert image.getpixel((48, 16))[3] == 0
                else:
                    assert image.convert("RGB").getpixel((48, 16)) == (255, 255, 255)
    print("SVG PNG/JPEG/WebP isolated smoke passed")


if __name__ == "__main__":
    main()
