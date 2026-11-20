"""Run in the packaged image with an isolated network and generated probe files."""

import importlib.util
import socket
import subprocess
import tempfile
from pathlib import Path

import pymupdf

root = Path("/workspace")
module_path = root / "src/i_love_open_converter/office_ops.py"
spec = importlib.util.spec_from_file_location("office_ops", module_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
fixtures = root / ".specs/features/office-to-pdf/probe-files"
assert {name for _, name in socket.if_nameindex()} == {"lo"}

with tempfile.TemporaryDirectory() as folder:
    folder = Path(folder)
    for name, expected in [
        ("word.docx", "Word probe content"),
        ("powerpoint.pptx", "PowerPoint probe content"),
        ("excel.xlsx", "Excel probe content"),
    ]:
        result = module.convert_office(fixtures / name, folder / name)
        with pymupdf.open(result) as pdf:
            assert expected in "".join(page.get_text() for page in pdf)
        print(name, "OK", flush=True)

    for name, ext, expected in [
        ("word.docx", "doc", "Word probe content"),
        ("powerpoint.pptx", "ppt", "PowerPoint probe content"),
        ("excel.xlsx", "xls", "Excel probe content"),
    ]:
        legacy = folder / "legacy"
        legacy.mkdir(exist_ok=True)
        subprocess.run(
            ["soffice", f"-env:UserInstallation={(folder / ext).as_uri()}", "--headless",
             "--convert-to", ext, "--outdir", str(legacy), str(fixtures / name)],
            check=True, timeout=60, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env={"HOME": str(folder), "PATH": "/usr/bin:/bin"},
        )
        source = legacy / (Path(name).stem + "." + ext)
        result = module.convert_office(source, folder / ("out-" + ext))
        with pymupdf.open(result) as pdf:
            assert expected in "".join(page.get_text() for page in pdf)
        print(source.name, "OK", flush=True)

    secret = folder / "other-job.txt"
    secret.write_text("other job data", encoding="utf-8")
    confined = folder / "current-job"
    confined.mkdir()
    result = subprocess.run(
        ["/app/.venv/bin/python", str(module_path.with_name("office_sandbox.py")),
         str(confined), "/usr/bin/cat", str(secret)],
        capture_output=True, timeout=10,
    )
    assert result.returncode != 0 and b"other job data" not in result.stdout
    print("other-job read denied", flush=True)

    result = subprocess.run(
        ["/app/.venv/bin/python", str(module_path.with_name("office_sandbox.py")),
         str(confined), "/usr/local/bin/python3", "-c",
         "import resource; print(resource.getrlimit(resource.RLIMIT_AS)[0], "
         "resource.getrlimit(resource.RLIMIT_FSIZE)[0])"],
        capture_output=True, timeout=10, check=True,
    )
    assert result.stdout.strip() == b"2147483648 268435456"
    print("resource limits enforced", flush=True)
