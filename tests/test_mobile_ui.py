from __future__ import annotations

import socket
import threading
import time
from contextlib import contextmanager
from urllib.error import URLError
from urllib.request import urlopen

import pytest
import uvicorn

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


@pytest.mark.parametrize(
    ("language", "guide_title", "succeeded_text", "download_text"),
    [
        ("pt-BR", "Comece em três passos", "Seus arquivos estão prontos.", "Baixar arquivo"),
        ("en", "Get started in three steps", "Your files are ready.", "Download file"),
    ],
)
def test_home_conversion_flow_is_usable_at_360px(
    settings, language, guide_title, succeeded_text, download_text
):
    with _serve_app(settings) as base_url, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport={"width": 360, "height": 900}, accept_downloads=True)
        page = context.new_page()

        def stub_job_api(route):
            request = route.request
            if request.method == "POST":
                body = request.post_data or ""
                assert "image.convert" in body
                assert '"format":"GIF"' in body
                route.fulfill(
                    status=202,
                    json={
                        "job_id": "mobile-review",
                        "status_url": "/api/jobs/mobile-review",
                    },
                )
            elif request.url.endswith("/download"):
                route.fulfill(
                    status=200,
                    body=b"GIF89a",
                    headers={
                        "Content-Type": "image/gif",
                        "Content-Disposition": 'attachment; filename="review.gif"',
                    },
                )
            else:
                route.fulfill(
                    status=200,
                    json={
                        "state": "succeeded",
                        "files": [{"name": "review.gif", "size_bytes": 6}],
                        "download_url": "/api/jobs/mobile-review/download",
                    },
                )

        try:
            page.route("**/api/jobs**", stub_job_api)
            page.goto(base_url, wait_until="networkidle")
            page.locator("#language").select_option(language)

            expect(page.locator("#first-use-title")).to_have_text(guide_title)
            expect(page.locator("#converter-title")).to_be_visible()
            expect(page.locator("#file-input")).to_be_visible()
            expect(page.locator("#output-format")).to_be_visible()
            page.locator("#output-format").select_option("GIF")
            assert page.evaluate("document.documentElement.scrollWidth === window.innerWidth")

            page.locator("#file-input").set_input_files(
                {"name": "source.jpg", "mimeType": "image/jpeg", "buffer": b"test image"}
            )
            page.locator("#submit-button").click()
            expect(page.locator("#job-status-text")).to_have_text(succeeded_text)
            expect(page.locator("#job-result")).to_be_visible()
            expect(page.locator("#result-name")).to_have_text("review.gif")
            download_link = page.get_by_role("link", name=download_text)
            expect(download_link).to_be_visible()
            assert page.evaluate("document.documentElement.scrollWidth === window.innerWidth")

            with page.expect_download() as download_info:
                download_link.click()
            assert download_info.value.suggested_filename == "review.gif"
        finally:
            context.close()
            browser.close()
