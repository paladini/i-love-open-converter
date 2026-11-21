from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

PACKAGES = {
    "translate-pb_en-1_9": "578e9c504595ac85f8e8e0b31e4f53c84e38e7638db8c3c8df384d05eac2671b",
    "translate-en_pb-1_9": "1d1cd5e9540c6b38c258bed002a42d3b311b8a189acb74feaa311ef30d175c5b",
}
BASE_URL = "https://data.argosopentech.com/argospm/v1/"
DESTINATION = Path(os.getenv("TRANSLATION_MODEL_DIR", "/opt/translation-models"))


def install(name: str, expected_hash: str) -> None:
    archive_name = f"{name}.argosmodel"
    DESTINATION.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        archive = Path(temporary) / archive_name
        digest = hashlib.sha256()
        with urllib.request.urlopen(BASE_URL + archive_name, timeout=120) as response:
            with archive.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    digest.update(chunk)
                    output.write(chunk)
        if digest.hexdigest() != expected_hash:
            raise SystemExit(f"SHA-256 mismatch for {archive_name}")
        target = DESTINATION / name
        target.mkdir(exist_ok=True)
        with zipfile.ZipFile(archive) as package:
            for member in package.infolist():
                path = PurePosixPath(member.filename)
                if path.is_absolute() or ".." in path.parts:
                    raise SystemExit(f"Unsafe path in {archive_name}")
                if not path.parts or path.parts[0] != name:
                    raise SystemExit(f"Unexpected package root in {archive_name}")
                relative_path = Path(*path.parts[1:])
                if not relative_path.parts:
                    continue
                mode = member.external_attr >> 16
                if mode & 0o170000 == 0o120000:
                    raise SystemExit(f"Symlink in {archive_name}")
                extracted = target / relative_path
                if member.is_dir():
                    extracted.mkdir(parents=True, exist_ok=True)
                else:
                    extracted.parent.mkdir(parents=True, exist_ok=True)
                    with package.open(member) as source, extracted.open("wb") as output:
                        shutil.copyfileobj(source, output)


for package_name, sha256 in PACKAGES.items():
    install(package_name, sha256)
