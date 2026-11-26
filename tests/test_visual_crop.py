from __future__ import annotations

import json
import socket
import threading
import time
from contextlib import contextmanager
from urllib.error import URLError
from urllib.request import urlopen

import pymupdf
import pytest
import uvicorn
from PIL import Image

from i_love_open_converter.main import create_app

playwright_api = pytest.importorskip(
    "playwright.sync_api", reason="install the dev group to run browser tests"
)
expect = playwright_api.expect
sync_playwright = playwright_api.sync_playwright


@contextmanager
def _serve_app(settings):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(("127.0.0.1", 0))
    server_socket.listen(128)
    base_url = f"http://127.0.0.1:{server_socket.getsockname()[1]}"
    server = uvicorn.Server(uvicorn.Config(create_app(settings), log_level="critical"))
    thread = threading.Thread(
        target=server.run,
        kwargs={"sockets": [server_socket]},
        daemon=True,
    )
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                with urlopen(f"{base_url}/", timeout=0.5) as response:
                    if response.status == 200:
                        break
            except (OSError, URLError):
                time.sleep(0.05)
        else:
            pytest.fail("The local test server did not start within 10 seconds")
        yield base_url
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        server_socket.close()


def _make_png(tmp_path, name: str = "sample.png", size: tuple[int, int] = (200, 100)) -> str:
    path = tmp_path / name
    Image.new("RGB", size, (40, 120, 210)).save(path, format="PNG")
    return str(path)


def _make_pdf(tmp_path, name: str = "sample.pdf", pages: int = 2) -> str:
    path = tmp_path / name
    doc = pymupdf.open()
    for index in range(pages):
        page = doc.new_page(width=300, height=400)
        page.insert_text((40, 60), f"Page {index + 1}")
    doc.save(path)
    doc.close()
    return str(path)


@pytest.mark.parametrize(
    "viewport",
    [{"width": 1280, "height": 900}, {"width": 360, "height": 900}],
)
def test_image_visual_crop_handles_sync_and_submit(settings, tmp_path, viewport):
    image_path = _make_png(tmp_path)
    submitted_options: list[dict] = []

    with _serve_app(settings) as base_url, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport=viewport)
        page = context.new_page()

        def stub_jobs(route):
            if route.request.method == "POST":
                body = route.request.post_data or ""
                assert "image.crop" in body
                marker = 'name="options"\r\n\r\n'
                if marker in body:
                    raw_options = body.split(marker, 1)[1].split("\r\n", 1)[0]
                    submitted_options.append(json.loads(raw_options))
                route.fulfill(
                    status=202,
                    json={"job_id": "img-crop-job", "status_url": "/api/jobs/img-crop-job"},
                )
            else:
                route.fulfill(
                    status=200,
                    json={
                        "job_id": "img-crop-job",
                        "state": "succeeded",
                        "files": [{"name": "sample.png", "size_bytes": 512}],
                        "download_url": "/api/jobs/img-crop-job/download",
                    },
                )

        page.route("**/api/jobs**", stub_jobs)
        page.goto(f"{base_url}/?tool=image.crop", wait_until="networkidle")
        page.set_input_files("#file-input", image_path)

        crop_editor = page.locator("#image-crop-editor")
        expect(crop_editor).to_be_visible()
        expect(crop_editor.locator(".cropper-container")).to_be_visible()
        assert crop_editor.locator(".cropper-point").count() == 8

        # Wait for Cropper to populate initial numeric inputs
        expect(page.locator("#crop-width")).not_to_have_value("")
        initial_width = int(page.locator("#crop-width").input_value())
        assert initial_width > 0

        # Drag southeast handle inward and verify inputs update
        se_handle = crop_editor.locator(".cropper-point.point-se")
        se_handle.scroll_into_view_if_needed()
        box = se_handle.bounding_box()
        assert box is not None
        cx = box["x"] + box["width"] / 2
        cy = box["y"] + box["height"] / 2
        page.mouse.move(cx, cy)
        page.mouse.down()
        page.mouse.move(cx - 24, cy - 12, steps=5)
        page.mouse.up()

        dragged_width = int(page.locator("#crop-width").input_value())
        assert dragged_width != initial_width

        # Edit numeric inputs directly and verify cropper box moves
        crop_box_before = crop_editor.locator(".cropper-crop-box").bounding_box()
        page.fill("#crop-left", "10")
        page.fill("#crop-top", "10")
        page.fill("#crop-width", "80")
        page.fill("#crop-height", "40")
        crop_box_after = crop_editor.locator(".cropper-crop-box").bounding_box()
        assert crop_box_before != crop_box_after

        # Aspect ratio 1:1 preset
        page.locator('[data-option="crop-aspect"] [data-crop-aspect="1"]').click()
        w_after_ratio = int(page.locator("#crop-width").input_value())
        h_after_ratio = int(page.locator("#crop-height").input_value())
        assert abs(w_after_ratio - h_after_ratio) <= 2

        page.click("#submit-button")
        expect(page.locator("#job-result")).to_be_visible()
        assert submitted_options
        assert int(submitted_options[0]["width"]) == w_after_ratio

        context.close()
        browser.close()


@pytest.mark.parametrize(
    "viewport",
    [{"width": 1280, "height": 900}, {"width": 360, "height": 900}],
)
def test_pdf_visual_crop_handles_sync_and_submit(settings, tmp_path, viewport):
    pdf_path = _make_pdf(tmp_path, pages=2)
    submitted_options: list[dict] = []

    with _serve_app(settings) as base_url, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport=viewport)
        page = context.new_page()

        def stub_jobs(route):
            if route.request.method == "POST":
                body = route.request.post_data or ""
                assert "pdf.crop" in body
                marker = 'name="options"\r\n\r\n'
                if marker in body:
                    raw_options = body.split(marker, 1)[1].split("\r\n", 1)[0]
                    submitted_options.append(json.loads(raw_options))
                route.fulfill(
                    status=202,
                    json={"job_id": "pdf-crop-job", "status_url": "/api/jobs/pdf-crop-job"},
                )
            else:
                route.fulfill(
                    status=200,
                    json={
                        "job_id": "pdf-crop-job",
                        "state": "succeeded",
                        "download_url": "/api/jobs/pdf-crop-job/download",
                    },
                )

        page.route("**/api/jobs**", stub_jobs)
        page.goto(f"{base_url}/tools/pdf-crop", wait_until="networkidle")
        page.set_input_files("#file", pdf_path)

        preview_area = page.locator(".crop-preview")
        expect(preview_area.locator(".cropper-container")).to_be_visible()
        assert preview_area.locator(".cropper-point").count() == 8

        # Drag northwest handle inward and verify #left / #top percentages increase
        nw_handle = preview_area.locator(".cropper-point.point-nw")
        nw_handle.scroll_into_view_if_needed()
        box = nw_handle.bounding_box()
        assert box is not None
        cx = box["x"] + box["width"] / 2
        cy = box["y"] + box["height"] / 2
        page.mouse.move(cx, cy)
        page.mouse.down()
        page.mouse.move(cx + 25, cy + 25, steps=5)
        page.mouse.up()

        assert float(page.locator("#left").input_value()) > 0
        assert float(page.locator("#top").input_value()) > 0

        # Edit percentage inputs directly and verify cropper updates
        crop_box_before = preview_area.locator(".cropper-crop-box").bounding_box()
        page.fill("#left", "15")
        page.fill("#top", "20")
        page.fill("#right", "85")
        page.fill("#bottom", "80")
        crop_box_after = preview_area.locator(".cropper-crop-box").bounding_box()
        assert crop_box_before != crop_box_after

        # Navigate to page 2 and verify Cropper re-initializes cleanly
        page.click("#next")
        expect(page.locator("#page-label")).to_contain_text("2")
        expect(preview_area.locator(".cropper-container")).to_be_visible()

        page.click("#submit")
        expect(page.locator("#download")).to_be_visible()
        assert submitted_options
        rect = submitted_options[0]["rectangle"]
        assert len(rect) == 4
        assert rect[0] < rect[2] and rect[1] < rect[3]

        context.close()
        browser.close()
