from __future__ import annotations

import shutil
import subprocess

import pymupdf
import pytest

import i_love_open_converter.ocr_ops as ocr_ops
from i_love_open_converter.ocr_ops import NoOcrTextError, OcrProcessingError


def _make_pdf(path, *, text=True, pages=1):
    document = pymupdf.open()
    for index in range(pages):
        page = document.new_page(width=240, height=120)
        if text:
            page.insert_text((25, 50), f"Searchable test {index + 1}")
    document.save(path)
    document.close()


def test_make_searchable_preserves_existing_text_and_uses_bounded_local_cli(tmp_path, monkeypatch):
    source = tmp_path / "source.pdf"
    destination = tmp_path / "output" / "searchable.pdf"
    _make_pdf(source, pages=2)
    seen = {}

    class FinishedProcess:
        def __init__(self, command, **kwargs):
            seen["command"] = command
            seen["kwargs"] = kwargs
            shutil.copyfile(command[-2], command[-1])

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def wait(self, timeout=None):
            seen["timeout"] = timeout
            return 0

    monkeypatch.setattr(ocr_ops.subprocess, "Popen", FinishedProcess)

    result = ocr_ops.make_searchable_pdf(source, destination, "por+eng")

    assert result == destination
    assert seen["command"][0:3] == [ocr_ops.sys.executable, "-m", "ocrmypdf"]
    assert seen["command"][-2:] == [str(source.resolve()), str(destination.resolve())]
    assert seen["command"][seen["command"].index("--language") + 1] == "por+eng"
    assert "--skip-text" in seen["command"] and "--optimize" in seen["command"]
    assert seen["command"][seen["command"].index("--jobs") + 1] == "1"
    assert seen["timeout"] == ocr_ops.OCR_TIMEOUT_SECONDS
    if ocr_ops.os.name == "nt":
        assert "creationflags" in seen["kwargs"]
    else:
        assert seen["kwargs"]["start_new_session"] is True
    with pymupdf.open(result) as document:
        assert document.page_count == 2
        assert [page.get_text("text").strip() for page in document] == [
            "Searchable test 1",
            "Searchable test 2",
        ]


def test_make_searchable_rejects_result_without_selectable_text_and_removes_it(
    tmp_path, monkeypatch
):
    source = tmp_path / "source.pdf"
    destination = tmp_path / "output.pdf"
    _make_pdf(source, text=False)

    class FinishedProcess:
        def __init__(self, command, **_kwargs):
            _make_pdf(command[-1], text=False)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def wait(self, *, timeout):
            return 0

    monkeypatch.setattr(ocr_ops.subprocess, "Popen", FinishedProcess)

    with pytest.raises(NoOcrTextError):
        ocr_ops.make_searchable_pdf(source, destination, "eng")

    assert not destination.exists()


def test_make_searchable_rejects_changed_visible_page_content(tmp_path, monkeypatch):
    source = tmp_path / "source.pdf"
    destination = tmp_path / "output.pdf"
    _make_pdf(source, text=False)

    class ChangedProcess:
        def __init__(self, command, **_kwargs):
            document = pymupdf.open()
            page = document.new_page(width=240, height=120)
            page.insert_text((25, 50), "Recognized text")
            document.save(command[-1])
            document.close()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(ocr_ops.subprocess, "Popen", ChangedProcess)

    with pytest.raises(OcrProcessingError):
        ocr_ops.make_searchable_pdf(source, destination, "eng")

    assert not destination.exists()


def test_make_searchable_timeout_kills_process_group_and_removes_partial_output(
    tmp_path, monkeypatch
):
    source = tmp_path / "source.pdf"
    destination = tmp_path / "output.pdf"
    _make_pdf(source)
    killed = []

    class TimedOutProcess:
        pid = 12345

        def __init__(self, command, **_kwargs):
            _make_pdf(command[-1])
            self.calls = 0

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def wait(self, timeout=None):
            self.calls += 1
            if self.calls == 1:
                assert timeout == ocr_ops.OCR_TIMEOUT_SECONDS
                raise subprocess.TimeoutExpired("ocrmypdf", timeout)
            return -9

        def kill(self):
            killed.append(self.pid)

    monkeypatch.setattr(ocr_ops.subprocess, "Popen", TimedOutProcess)
    if ocr_ops.os.name != "nt":
        monkeypatch.setattr(ocr_ops.os, "killpg", lambda pid, signal: killed.append((pid, signal)))

    with pytest.raises(OcrProcessingError):
        ocr_ops.make_searchable_pdf(source, destination, "por")

    if ocr_ops.os.name == "nt":
        assert killed == [12345]
    else:
        assert killed == [(12345, ocr_ops.signal.SIGKILL)]
    assert not destination.exists()
