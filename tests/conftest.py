from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image

from i_love_open_converter.config import Settings


@pytest.fixture
def settings(tmp_path):
    return Settings(data_dir=tmp_path / "data", max_file_size_mb=1, max_total_upload_mb=2)


@pytest.fixture
def jpeg_bytes():
    buffer = BytesIO()
    Image.new("RGB", (16, 12), (80, 120, 180)).save(buffer, format="JPEG")
    return buffer.getvalue()
