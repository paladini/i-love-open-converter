from __future__ import annotations

import pytest
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps

from i_love_open_converter.image_ops import (
    InvalidImageError,
    UnsupportedImageError,
    _fit_meme_caption,
    convert_image,
    inspect_image,
    process_image,
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


def test_image_compression_applies_the_requested_jpeg_quality(tmp_path):
    source = tmp_path / "noise.png"
    low_quality = tmp_path / "low.jpg"
    high_quality = tmp_path / "high.jpg"
    Image.effect_noise((128, 128), 90).convert("RGB").save(source)

    process_image(source, low_quality, "image.compress", {"format": "JPEG", "quality": 25})
    process_image(source, high_quality, "image.compress", {"format": "JPEG", "quality": 90})

    with Image.open(low_quality) as low, Image.open(high_quality) as high:
        assert sum(low.quantization[0]) > sum(high.quantization[0])


@pytest.mark.parametrize(
    ("output_format", "expected_mime", "expected_mode"),
    [("PNG", "image/png", "RGBA"), ("WEBP", "image/webp", "RGBA"), ("JPEG", "image/jpeg", "RGB")],
)
def test_meme_captions_preserve_dimensions_and_alpha_or_flatten_for_jpeg(
    tmp_path, output_format, expected_mime, expected_mode
):
    source = tmp_path / "transparent.png"
    destination = tmp_path / f"meme.{output_format.lower()}"
    image = Image.new("RGBA", (160, 100), (30, 80, 200, 0))
    image.save(source)

    mime, size = process_image(
        source,
        destination,
        "image.meme",
        {"format": output_format, "top_text": "THIS IS A MEME", "bottom_text": "WITH TWO CAPTIONS"},
    )

    assert mime == expected_mime
    assert size == destination.stat().st_size
    with Image.open(destination) as result:
        assert result.size == (160, 100)
        assert result.mode == expected_mode
        if expected_mode == "RGBA":
            assert result.getchannel("A").getextrema() != (0, 0)
        else:
            assert result.getpixel((159, 50)) == (255, 255, 255)


def test_meme_long_captions_fit_small_images_and_mark_truncated_text(tmp_path):
    source = tmp_path / "small.png"
    destination = tmp_path / "small-meme.png"
    Image.new("RGBA", (80, 60), (0, 0, 0, 0)).save(source)

    process_image(
        source,
        destination,
        "image.meme",
        {"format": "PNG", "top_text": "TOP " * 75, "bottom_text": "BOTTOM " * 75},
    )

    with Image.open(destination) as result:
        alpha = result.getchannel("A")
        top = alpha.crop((0, 0, 80, 30)).getbbox()
        bottom = alpha.crop((0, 30, 80, 60)).getbbox()
        assert result.size == (80, 60)
        assert top is not None
        assert bottom is not None
        assert top[3] <= 30
        assert bottom[3] <= 30


def test_meme_applies_exif_orientation_before_drawing_captions(tmp_path):
    source = tmp_path / "rotated.jpg"
    destination = tmp_path / "oriented-meme.png"
    original = Image.new("RGB", (40, 80), "blue")
    exif = Image.Exif()
    exif[274] = 6
    original.save(source, format="JPEG", exif=exif)
    original.close()
    with Image.open(source) as opened:
        baseline = ImageOps.exif_transpose(opened).convert("RGBA")

    process_image(
        source,
        destination,
        "image.meme",
        {"format": "PNG", "top_text": "EXIF"},
    )

    with Image.open(destination) as result:
        changed = [
            (x, y)
            for y in range(result.height)
            for x in range(result.width)
            if result.getpixel((x, y)) != baseline.getpixel((x, y))
        ]
        assert result.size == (80, 40)
        assert changed
        assert all(y < 20 for _, y in changed)
    baseline.close()


def test_meme_caption_is_centered_bold_and_has_a_dark_outline(tmp_path):
    source = tmp_path / "plain.png"
    destination = tmp_path / "styled.png"
    base = Image.new("RGB", (160, 100), (127, 127, 127))
    base.save(source)
    process_image(source, destination, "image.meme", {"format": "PNG", "top_text": "TEST"})

    with Image.open(destination) as rendered:
        top = rendered.convert("RGB").crop((0, 0, 160, 50))
        diff = ImageChops.difference(base, rendered.convert("RGB")).convert("L")
        bbox = diff.crop((0, 0, 160, 50)).getbbox()
        assert bbox is not None
        assert abs((bbox[0] + bbox[2]) / 2 - 80) <= 2
        top_pixels = list(top.get_flattened_data())
        assert (0, 0, 0) in top_pixels
        assert (255, 255, 255) in top_pixels

        regular = Image.new("RGB", (160, 100), (127, 127, 127))
        regular_draw = ImageDraw.Draw(regular)
        font = ImageFont.load_default(size=20)
        bounds = regular_draw.textbbox((0, 0), "TEST", font=font)
        x = (160 - (bounds[2] - bounds[0])) // 2 - bounds[0]
        regular_draw.text((x, 2), "TEST", font=font, fill="white")
        regular_white = sum(
            pixel == (255, 255, 255) for pixel in regular.crop((0, 0, 160, 50)).get_flattened_data()
        )
        styled_white = sum(pixel == (255, 255, 255) for pixel in top_pixels)
        assert styled_white > regular_white
    base.close()


def test_meme_caption_fit_wraps_and_marks_text_that_cannot_fit():
    image = Image.new("RGB", (80, 60), "gray")
    draw = ImageDraw.Draw(image)

    font, lines, line_height = _fit_meme_caption(
        draw, "LONG CAPTION " * 25, max_width=72, max_height=4, base_font_size=12
    )

    assert len(lines) == 2
    assert lines[-1].endswith("…")
    assert all(draw.textlength(line, font=font) <= 72 for line in lines)
    assert len(lines) * line_height <= 4
    image.close()


@pytest.mark.parametrize("scale", [2, 4])
@pytest.mark.parametrize(
    ("output_format", "expected_mode"), [("PNG", "RGBA"), ("WEBP", "RGBA"), ("JPEG", "RGB")]
)
def test_upscale_uses_selected_dimensions_and_preserves_alpha(
    tmp_path, scale, output_format, expected_mode
):
    source = tmp_path / "transparent.png"
    destination = tmp_path / f"upscaled.{output_format.lower()}"
    image = Image.new("RGBA", (8, 6), (220, 30, 50, 0))
    for x in range(4, 8):
        for y in range(6):
            image.putpixel((x, y), (220, 30, 50, 255))
    image.save(source)

    process_image(
        source,
        destination,
        "image.upscale",
        {"format": output_format, "scale": scale},
    )

    with Image.open(destination) as result:
        assert result.size == (8 * scale, 6 * scale)
        assert result.mode == expected_mode
        if expected_mode == "RGBA":
            assert result.getchannel("A").getextrema() == (0, 255)
        else:
            assert min(result.getpixel((1, 5))) > 240
    image.close()


def test_upscale_converts_palette_transparency_before_lanczos_resampling(tmp_path):
    source = tmp_path / "palette.png"
    destination = tmp_path / "palette-upscaled.png"
    image = Image.new("P", (8, 6), 0)
    image.putpalette([255, 0, 0, 0, 0, 255] + [0, 0, 0] * 254)
    for x in range(4, 8):
        for y in range(6):
            image.putpixel((x, y), 1)
    image.save(source, transparency=0)

    process_image(source, destination, "image.upscale", {"format": "PNG", "scale": 2})

    with Image.open(destination) as result:
        assert result.mode == "RGBA"
        assert result.size == (16, 12)
        assert result.getchannel("A").getextrema() == (0, 255)
    image.close()


def test_upscale_applies_exif_orientation_before_multiplying_dimensions(tmp_path):
    source = tmp_path / "rotated.jpg"
    destination = tmp_path / "oriented-upscale.png"
    image = Image.new("RGB", (8, 12), "blue")
    exif = Image.Exif()
    exif[274] = 6
    image.save(source, format="JPEG", exif=exif)
    image.close()

    process_image(source, destination, "image.upscale", {"format": "PNG", "scale": 2})

    with Image.open(destination) as result:
        assert result.size == (24, 16)
