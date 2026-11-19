from __future__ import annotations

from io import BytesIO

import pymupdf
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


@pytest.fixture
def pdf_bytes():
    document = pymupdf.open()
    for index in range(2):
        page = document.new_page(width=240, height=120)
        page.insert_text((30, 50), f"Test page {index + 1}")
    data = document.tobytes()
    document.close()
    return data
