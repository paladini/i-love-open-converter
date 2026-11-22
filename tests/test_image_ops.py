from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps

import i_love_open_converter.image_ops as image_ops
from i_love_open_converter.image_ops import (
    InvalidImageError,
    NoFacesDetectedError,
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
    first = Image.new("RGB", (3, 2), "red")
    second = Image.new("RGB", (3, 2), "blue")
    first.save(source, format="GIF", save_all=True, append_images=[second], duration=100)

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


def test_upscale_uses_lanczos_then_fixed_unsharp_mask(tmp_path, monkeypatch):
    source = tmp_path / "source.png"
    destination = tmp_path / "upscaled.png"
    Image.new("RGB", (8, 6), (20, 60, 100)).save(source)
    events = []
    original_resize = Image.Image.resize
    original_sharpen = image_ops._apply_unsharp_mask

    def track_resize(image, size, resample=None, **kwargs):
        if size == (16, 12):
            events.append(("resize", resample))
        return original_resize(image, size, resample=resample, **kwargs)

    def track_sharpen(image):
        events.append(("sharpen",))
        return original_sharpen(image)

    monkeypatch.setattr(Image.Image, "resize", track_resize)
    monkeypatch.setattr(image_ops, "_apply_unsharp_mask", track_sharpen)

    process_image(source, destination, "image.upscale", {"format": "PNG", "scale": 2})

    assert events == [
        ("resize", Image.Resampling.LANCZOS),
        ("sharpen",),
    ]


def test_background_removal_uses_one_cached_local_session(tmp_path, monkeypatch):
    source = tmp_path / "source.png"
    Image.new("RGB", (8, 6), "blue").save(source)
    sessions = []
    used_sessions = []

    def new_session(model):
        sessions.append(model)
        return object()

    def remove(image, *, session, post_process_mask):
        used_sessions.append((session, post_process_mask))
        return image.convert("RGBA")

    monkeypatch.setitem(
        sys.modules,
        "rembg",
        SimpleNamespace(new_session=new_session, remove=remove),
    )
    monkeypatch.setattr(image_ops, "_BACKGROUND_SESSION", None)

    for index in range(2):
        process_image(
            source,
            tmp_path / f"cutout-{index}.png",
            "image.remove_background",
            {"format": "PNG"},
        )

    assert sessions == ["u2netp"]
    assert len(used_sessions) == 2
    assert used_sessions[0][0] is used_sessions[1][0]
    assert all(post_process for _, post_process in used_sessions)
    for index in range(2):
        with Image.open(tmp_path / f"cutout-{index}.png") as result:
            assert result.mode == "RGBA"
            assert result.size == (8, 6)


def test_background_removal_applies_exif_orientation_before_inference(tmp_path, monkeypatch):
    source = tmp_path / "rotated.jpg"
    destination = tmp_path / "cutout.png"
    original = Image.new("RGB", (8, 12), "blue")
    exif = Image.Exif()
    exif[274] = 6
    original.save(source, exif=exif)
    original.close()
    seen_sizes = []

    def fake_remove(image):
        seen_sizes.append(image.size)
        return image.convert("RGBA")

    monkeypatch.setattr(image_ops, "_remove_image_background", fake_remove)

    process_image(source, destination, "image.remove_background", {"format": "PNG"})

    assert seen_sizes == [(12, 8)]
    with Image.open(destination) as result:
        assert result.size == (12, 8)
        assert result.mode == "RGBA"


def test_face_blur_blurs_detected_region_and_preserves_dimensions(tmp_path, monkeypatch):
    source = tmp_path / "source.png"
    destination = tmp_path / "blurred.png"
    image = Image.new("RGB", (100, 80), "white")
    ImageDraw.Draw(image).rectangle((30, 20, 49, 39), fill="black")
    image.save(source)
    monkeypatch.setattr(image_ops, "_detect_face_regions", lambda _image: [(30, 20, 50, 40)])

    process_image(source, destination, "image.blur_faces", {"format": "PNG"})

    with Image.open(destination) as result:
        assert result.size == (100, 80)
        assert result.getpixel((10, 10)) == (255, 255, 255)
        assert result.getpixel((40, 30)) != (0, 0, 0)


def test_face_blur_applies_exif_orientation_before_detection(tmp_path, monkeypatch):
    source = tmp_path / "rotated.jpg"
    destination = tmp_path / "oriented-blur.png"
    original = Image.new("RGB", (8, 12), "blue")
    exif = Image.Exif()
    exif[274] = 6
    original.save(source, exif=exif)
    original.close()
    seen_sizes = []

    def detect(image):
        seen_sizes.append(image.size)
        return [(2, 2, 8, 8)]

    monkeypatch.setattr(image_ops, "_detect_face_regions", detect)

    process_image(source, destination, "image.blur_faces", {"format": "PNG"})

    assert seen_sizes == [(12, 8)]
    with Image.open(destination) as result:
        assert result.size == (12, 8)


def test_face_blur_fails_when_no_faces_are_detected(tmp_path, monkeypatch):
    source = tmp_path / "source.png"
    destination = tmp_path / "blurred.png"
    Image.new("RGB", (8, 6), "white").save(source)
    monkeypatch.setattr(image_ops, "_detect_face_regions", lambda _image: [])

    with pytest.raises(NoFacesDetectedError):
        process_image(source, destination, "image.blur_faces", {"format": "PNG"})

    assert not destination.exists()


def test_manual_region_blur_only_changes_selected_area_and_preserves_size(tmp_path):
    source = tmp_path / "source.png"
    destination = tmp_path / "blurred.png"
    image = Image.new("RGB", (40, 30), "white")
    ImageDraw.Draw(image).rectangle((10, 8, 25, 22), fill="black")
    image.save(source)

    process_image(
        source,
        destination,
        "image.blur_regions",
        {"format": "PNG", "regions": [{"x": 0.2, "y": 0.2, "width": 0.4, "height": 0.5}]},
    )

    with Image.open(destination) as result:
        assert result.size == (40, 30)
        assert result.getpixel((2, 2)) == (255, 255, 255)
        assert result.getpixel((17, 15)) != (0, 0, 0)


@pytest.mark.parametrize(
    "regions",
    [
        [],
        [{"x": 0, "y": 0, "width": 1, "height": 1, "extra": True}],
        [{"x": -0.1, "y": 0, "width": 0.2, "height": 0.2}],
        [{"x": 0.9, "y": 0.9, "width": 0.2, "height": 0.2}],
        [{"x": 0, "y": 0, "width": 0.01, "height": 0.2}],
        [{"x": True, "y": 0, "width": 0.2, "height": 0.2}],
    ],
)
def test_manual_blur_regions_reject_invalid_rectangles(regions):
    with pytest.raises(image_ops.InvalidImageOptionsError):
        image_ops.validate_image_blur_regions(regions, 100, 80)


def test_manual_blur_regions_reject_more_than_twenty_rectangles():
    regions = [{"x": 0, "y": 0, "width": 0.1, "height": 0.1}] * 21
    with pytest.raises(image_ops.InvalidImageOptionsError):
        image_ops.validate_image_blur_regions(regions, 100, 80)


def test_plate_blur_fails_when_detection_is_empty(tmp_path, monkeypatch):
    source = tmp_path / "source.png"
    destination = tmp_path / "blurred.png"
    Image.new("RGB", (8, 6), "white").save(source)
    monkeypatch.setattr(image_ops, "_detect_plate_regions", lambda _image: [])

    with pytest.raises(image_ops.NoPlatesDetectedError):
        process_image(source, destination, "image.blur_plates", {"format": "PNG"})

    assert not destination.exists()


def test_plate_blur_blurs_detected_region_and_preserves_size(tmp_path, monkeypatch):
    source = tmp_path / "source.png"
    destination = tmp_path / "blurred.png"
    image = Image.new("RGB", (100, 80), "white")
    ImageDraw.Draw(image).rectangle((30, 20, 49, 39), fill="black")
    image.save(source)
    monkeypatch.setattr(image_ops, "_detect_plate_regions", lambda _image: [(30, 20, 50, 40)])

    process_image(source, destination, "image.blur_plates", {"format": "PNG"})

    with Image.open(destination) as result:
        assert result.size == (100, 80)
        assert result.getpixel((5, 5)) == (255, 255, 255)
        assert result.getpixel((40, 30)) != (0, 0, 0)


def test_bundled_plate_cascades_load_and_detect_on_local_image():
    image = Image.new("RGB", (800, 600), "white")

    cv2, cascades = image_ops._plate_cascades()
    regions = image_ops._detect_plate_regions(image)

    assert cv2.__file__
    assert cascades
    assert any(not cascade.empty() for cascade in cascades)
    assert regions == []
