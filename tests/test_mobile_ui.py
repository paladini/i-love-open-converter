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


def test_pdf_compression_profile_is_localized_and_submitted(settings, pdf_bytes):
    with _serve_app(settings) as base_url, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()

        def stub_job_api(route):
            request = route.request
            if request.method == "POST":
                body = request.post_data or ""
                assert '"profile":"extreme"' in body
                route.fulfill(
                    status=202,
                    json={
                        "job_id": "compression-profile",
                        "status_url": "/api/jobs/compression-profile",
                    },
                )
            else:
                route.fulfill(
                    status=200,
                    json={
                        "state": "succeeded",
                        "files": [{"name": "compressed.pdf", "size_bytes": 100}],
                        "download_url": "/api/jobs/compression-profile/download",
                    },
                )

        try:
            page.route("**/api/jobs**", stub_job_api)
            page.goto(base_url, wait_until="networkidle")
            page.locator('[data-tool="pdf.compress"]').click()
            profile = page.locator("#pdf-compression-profile")
            expect(profile).to_be_visible()
            expect(profile).to_have_value("lossless")
            expect(profile.locator('option[value="lossless"]')).to_have_text("Lossless")
            page.locator("#language").select_option("pt-BR")
            expect(page.locator('[data-option="pdf-compression-profile"] span')).to_have_text(
                "Perfil de compressão"
            )
            expect(profile.locator('option[value="recommended"]')).to_have_text("Recomendado")
            page.locator("#language").select_option("en")
            profile.select_option("extreme")
            page.locator("#file-input").set_input_files(
                {"name": "source.pdf", "mimeType": "application/pdf", "buffer": pdf_bytes}
            )
            page.locator("#submit-button").click()
            expect(page.locator("#job-result")).to_be_visible()
        finally:
            context.close()
            browser.close()


def test_pdf_compression_accepts_multiple_files_in_selection_order(settings, pdf_bytes):
    with _serve_app(settings) as base_url, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()

        def stub_job_api(route):
            request = route.request
            if request.method == "POST":
                body = request.post_data or ""
                assert body.count('name="files"') == 2
                route.fulfill(
                    status=202,
                    json={
                        "job_id": "compression-batch",
                        "status_url": "/api/jobs/compression-batch",
                    },
                )
            else:
                route.fulfill(
                    status=200,
                    json={
                        "state": "succeeded",
                        "files": [{"name": "converted-files.zip", "size_bytes": 200}],
                        "download_url": "/api/jobs/compression-batch/download",
                    },
                )

        try:
            page.route("**/api/jobs**", stub_job_api)
            page.goto(base_url, wait_until="networkidle")
            page.locator('[data-tool="pdf.compress"]').click()
            file_input = page.locator("#file-input")
            assert file_input.evaluate("input => input.multiple")
            file_input.set_input_files(
                [
                    {"name": "first.pdf", "mimeType": "application/pdf", "buffer": pdf_bytes},
                    {"name": "second.pdf", "mimeType": "application/pdf", "buffer": pdf_bytes},
                ]
            )
            expect(page.locator("#selected-file-name li").nth(0)).to_contain_text("first.pdf")
            expect(page.locator("#selected-file-name li").nth(1)).to_contain_text("second.pdf")
            page.locator("#submit-button").click()
            expect(page.locator("#job-result")).to_be_visible()
        finally:
            context.close()
            browser.close()


@pytest.mark.parametrize(
    ("tool", "operation"),
    [
        ("html-to-pdf", "html.to_pdf"),
        ("html-to-image", "html.to_image"),
    ],
)
@pytest.mark.parametrize("language", ["pt-BR", "en"])
def test_public_url_conversion_controls_are_usable_at_360px(settings, tool, operation, language):
    done_text = (
        "Seu PDF est\u00e1 pronto."
        if operation == "html.to_pdf" and language == "pt-BR"
        else "Your PDF is ready."
        if operation == "html.to_pdf"
        else "Suas imagens est\u00e3o prontas."
        if language == "pt-BR"
        else "Your images are ready."
    )
    with _serve_app(settings) as base_url, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport={"width": 360, "height": 800})
        page = context.new_page()

        def stub_job_api(route):
            request = route.request
            if request.method == "POST":
                body = request.post_data or ""
                assert operation in body
                assert "https://public.example/guide" in body
                route.fulfill(
                    status=202,
                    json={"job_id": "url-review", "status_url": "/api/jobs/url-review"},
                )
            else:
                route.fulfill(
                    status=200,
                    json={
                        "state": "succeeded",
                        "files": [{"name": "converted-result.pdf", "size_bytes": 12}],
                        "download_url": "/api/jobs/url-review/download",
                    },
                )

        try:
            page.route("**/api/jobs**", stub_job_api)
            page.goto(f"{base_url}/tools/{tool}", wait_until="networkidle")
            page.locator("#language").select_option(language)
            page.locator('input[name="source-mode"][value="url"]').check()
            expect(page.locator("#url")).to_be_visible()
            expect(page.locator("#file")).to_be_hidden()
            page.locator("#url").fill("https://public.example/guide")
            if operation == "html.to_image":
                page.locator("#format").select_option("svg")
            assert page.evaluate("document.documentElement.scrollWidth === window.innerWidth")
            page.locator("#submit").click()
            expect(page.locator("#message")).to_have_text(done_text, timeout=5000)
            expect(page.locator("#download")).to_be_visible()
            assert page.evaluate("document.documentElement.scrollWidth === window.innerWidth")
        finally:
            context.close()
            browser.close()
