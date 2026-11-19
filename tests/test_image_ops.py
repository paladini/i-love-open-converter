from __future__ import annotations

import pytest
from PIL import Image

from i_love_open_converter.image_ops import (
    InvalidImageError,
    UnsupportedImageError,
    convert_image,
    inspect_image,
)


def test_inspect_image_uses_the_file_content(tmp_path):
    source = tmp_path / "looks-like-jpeg.jpg"
    Image.new("RGB", (3, 2), "red").save(source, format="PNG")

    image_format, mime_type = inspect_image(source)

    assert image_format == "PNG"
    assert mime_type == "image/png"


def test_convert_image_writes_requested_format_and_size(tmp_path):
    source = tmp_path / "source.png"
    destination = tmp_path / "converted.webp"
    Image.new("RGB", (11, 7), (30, 90, 140)).save(source, format="PNG")

    mime_type, size_bytes = convert_image(source, destination, "WEBP")

    assert mime_type == "image/webp"
    assert size_bytes == destination.stat().st_size
    with Image.open(destination) as converted:
        assert converted.format == "WEBP"
        assert converted.size == (11, 7)


def test_convert_image_flattens_transparency_to_white_for_jpeg(tmp_path):
    source = tmp_path / "transparent.png"
    destination = tmp_path / "opaque.jpg"
    image = Image.new("RGBA", (2, 1), (255, 0, 0, 0))
    image.save(source, format="PNG")

    convert_image(source, destination, "JPEG")

    with Image.open(destination) as converted:
        assert converted.mode == "RGB"
        assert converted.getpixel((0, 0)) == (255, 255, 255)


def test_inspect_image_rejects_invalid_content(tmp_path):
    source = tmp_path / "broken.jpg"
    source.write_bytes(b"not an image")

    with pytest.raises(InvalidImageError):
        inspect_image(source)


def test_inspect_image_rejects_unsupported_image_format(tmp_path):
    source = tmp_path / "animated.gif"
    Image.new("RGB", (3, 2), "red").save(source, format="GIF")

    with pytest.raises(UnsupportedImageError):
        inspect_image(source)
