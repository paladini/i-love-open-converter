from __future__ import annotations

import re
import unicodedata
from pathlib import Path, PurePosixPath


def safe_filename(filename: str, fallback: str = "arquivo") -> str:
    normalized = unicodedata.normalize("NFKC", filename).replace("\\", "/")
    basename = PurePosixPath(normalized).name
    basename = "".join(char for char in basename if char.isprintable())
    basename = re.sub(r"[<>:\"|?*/\\]+", "_", basename).strip(" .")
    if basename in {"", ".", ".."}:
        basename = fallback
    return basename[:180]


def safe_stem(filename: str) -> str:
    stem = Path(safe_filename(filename)).stem
    return safe_filename(stem or "arquivo")
