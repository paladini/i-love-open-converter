from __future__ import annotations

import pytest

from i_love_open_converter.svg_ops import (
    MAX_SVG_PIXELS,
    InvalidSvgError,
    SvgUnavailableError,
    _validate_static_svg,
    inspect_svg,
)


def test_inspect_svg_uses_view_box_when_dimensions_are_missing(tmp_path):
    source = tmp_path / "viewbox.svg"
    source.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 480"/>',
        encoding="utf-8",
    )

    assert inspect_svg(source) == (640, 480)


def test_inspect_svg_uses_default_size_without_dimensions(tmp_path):
    source = tmp_path / "default.svg"
    source.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8")

    assert inspect_svg(source) == (300, 150)


def test_inspect_svg_converts_css_units_and_caps_pixels():
    content = (
        b'<svg xmlns="http://www.w3.org/2000/svg" width="25.4mm" height="25.4mm"/>'
    )
    _, width, height = _validate_static_svg(content)
    assert (width, height) == (96, 96)

    oversized = (
        b'<svg xmlns="http://www.w3.org/2000/svg" width="100000px" height="100000px"/>'
    )
    _, width, height = _validate_static_svg(oversized)
    assert width * height <= MAX_SVG_PIXELS
    assert width / height == pytest.approx(1)


@pytest.mark.parametrize(
    "markup",
    [
        '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
        '<svg xmlns="http://www.w3.org/2000/svg"><animate attributeName="x"/></svg>',
        '<svg xmlns="http://www.w3.org/2000/svg"><foreignObject/></svg>',
        '<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"/>',
        '<svg xmlns="http://www.w3.org/2000/svg"><image href="https://example.com/a.png"/></svg>',
        '<svg xmlns="http://www.w3.org/2000/svg"><style>image{fill:url(file:///etc/passwd)}</style></svg>',
        '<!DOCTYPE svg [<!ENTITY x "bad">]><svg xmlns="http://www.w3.org/2000/svg"/>',
        '<html/>',
    ],
)
def test_svg_inspection_rejects_unsafe_or_non_svg_content(markup):
    with pytest.raises(InvalidSvgError):
        _validate_static_svg(markup.encode())


def test_inspect_svg_rejects_files_over_ten_mib(tmp_path):
    source = tmp_path / "large.svg"
    source.write_bytes(b" " * (10 * 1024 * 1024 + 1))

    with pytest.raises(InvalidSvgError):
        inspect_svg(source)


def test_svg_conversion_requires_isolated_linux_worker(tmp_path, monkeypatch):
    from i_love_open_converter import svg_ops

    source = tmp_path / "source.svg"
    source.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8")
    monkeypatch.setattr(svg_ops, "office_isolated", lambda: False)

    with pytest.raises(SvgUnavailableError):
        svg_ops.convert_svg_to_image(source, tmp_path / "result.png", "PNG", 300, 150)


def test_static_svg_has_no_network_or_runtime_asset_dependencies():
    # The sanitizer accepts a local vector gradient, but rejects references that could fetch a URL.
    safe = b'<svg xmlns="http://www.w3.org/2000/svg"><defs><linearGradient id="g"/></defs></svg>'
    assert _validate_static_svg(safe)[1:] == (300, 150)

