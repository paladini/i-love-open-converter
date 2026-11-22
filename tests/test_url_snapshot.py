from __future__ import annotations

import base64
import re
import socket

import pytest

from i_love_open_converter import url_snapshot
from i_love_open_converter.url_snapshot import UrlSnapshotError, _Response


def test_url_snapshot_rejects_loopback_and_non_web_ports():
    with pytest.raises(UrlSnapshotError):
        url_snapshot._validate_and_resolve("http://127.0.0.1/admin")
    with pytest.raises(UrlSnapshotError):
        url_snapshot._validate_and_resolve("https://example.com:8443/")
    with pytest.raises(UrlSnapshotError):
        url_snapshot._validate_and_resolve("https://user:secret@example.com/")


def test_url_snapshot_rejects_redirect_over_limit(monkeypatch):
    connected = []

    class RedirectResponse:
        status = 302

        @staticmethod
        def getheader(name):
            return "https://public.example/next" if name == "Location" else None

        @staticmethod
        def close():
            pass

    class RedirectConnection:
        def __init__(self, *args):
            connected.append(args[0])
            self.sock = object()

        @staticmethod
        def request(*args, **kwargs):
            pass

        @staticmethod
        def getresponse():
            return RedirectResponse()

        @staticmethod
        def close():
            pass

    monkeypatch.setattr(
        url_snapshot,
        "_validate_and_resolve",
        lambda url, timeout: ("https", 443, "public.example", "93.184.216.34"),
    )
    monkeypatch.setattr(url_snapshot, "_PinnedHTTPSConnection", RedirectConnection)
    with pytest.raises(UrlSnapshotError):
        url_snapshot._get("https://public.example/start", url_snapshot.time.monotonic() + 10, 1000)
    assert len(connected) == url_snapshot.MAX_URL_REDIRECTS + 1


def test_public_html_snapshot_enforces_resource_limit(monkeypatch):
    monkeypatch.setattr(url_snapshot, "MAX_URL_RESOURCES", 2)
    requested = []
    responses = {
        "https://public.example/page": _Response(
            b'<img src="/one.png"><img src="/two.png">',
            "text/html",
            "https://public.example/page",
        ),
        "https://public.example/one.png": _Response(
            b"one", "image/png", "https://public.example/one.png"
        ),
        "https://public.example/two.png": _Response(
            b"two", "image/png", "https://public.example/two.png"
        ),
    }

    def fetch(url, *_):
        requested.append(url)
        return responses[url]

    monkeypatch.setattr(url_snapshot, "_get", fetch)
    with pytest.raises(url_snapshot.UrlSnapshotTooLargeError):
        url_snapshot.fetch_public_html("https://public.example/page")
    assert requested == ["https://public.example/page", "https://public.example/one.png"]


def test_public_html_snapshot_enforces_aggregate_byte_limit(monkeypatch):
    monkeypatch.setattr(url_snapshot, "MAX_URL_TOTAL_BYTES", 20)
    responses = {
        "https://public.example/page": _Response(b"<img src='/one.png'>", "text/html", "https://public.example/page"),
        "https://public.example/one.png": _Response(
            b"12345678901", "image/png", "https://public.example/one.png"
        ),
    }
    monkeypatch.setattr(url_snapshot, "_get", lambda url, *_: responses[url])
    with pytest.raises(url_snapshot.UrlSnapshotTooLargeError):
        url_snapshot.fetch_public_html("https://public.example/page")


def test_public_html_snapshot_enforces_total_deadline_after_fetch(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(url_snapshot.time, "monotonic", lambda: now[0])

    def slow_fetch(*args):
        now[0] += url_snapshot.URL_FETCH_TIMEOUT_SECONDS + 1
        return _Response(b"<p>slow</p>", "text/html", "https://public.example/page")

    monkeypatch.setattr(url_snapshot, "_get", slow_fetch)
    with pytest.raises(url_snapshot.UrlSnapshotTooLargeError):
        url_snapshot.fetch_public_html("https://public.example/page")


def test_url_snapshot_rejects_a_hostname_with_any_private_dns_answer(monkeypatch):
    def resolve(*args, **kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.4", 443)),
        ]

    monkeypatch.setattr(url_snapshot.socket, "getaddrinfo", resolve)
    with pytest.raises(UrlSnapshotError):
        url_snapshot._validate_and_resolve("https://public.example/")


def test_public_html_snapshot_inlines_static_css_and_images_and_removes_scripts(monkeypatch):
    responses = {
        "https://public.example/page": _Response(
            b'<link rel="stylesheet" href="/site.css"><img src="/cover.png">'
            b"<script>document.body.innerHTML='unsafe'</script>",
            "text/html",
            "https://public.example/page",
        ),
        "https://public.example/site.css": _Response(
            b'body { background-image: url("/background.png") }',
            "text/css",
            "https://public.example/site.css",
        ),
        "https://public.example/cover.png": _Response(b"cover", "image/png", "https://public.example/cover.png"),
        "https://public.example/background.png": _Response(
            b"background", "image/png", "https://public.example/background.png"
        ),
    }
    requested = []

    def fetch(url, deadline, limit):
        requested.append(url)
        return responses[url]

    monkeypatch.setattr(url_snapshot, "_get", fetch)
    result = url_snapshot.fetch_public_html("https://public.example/page")

    assert b"<script" not in result
    assert b"data:text/css" in result
    css_match = re.search(rb'href="data:text/css;charset=utf-8;base64,([^\"]+)"', result)
    assert css_match is not None
    css = base64.b64decode(css_match.group(1))
    assert b"data:image/png;base64," in css
    assert b'data:image/png;base64,' in result
    assert requested == [
        "https://public.example/page",
        "https://public.example/site.css",
        "https://public.example/background.png",
        "https://public.example/cover.png",
    ]


def test_public_html_snapshot_rejects_non_html_main_response(monkeypatch):
    monkeypatch.setattr(
        url_snapshot,
        "_get",
        lambda *args: _Response(b"%PDF-1.7", "application/pdf", "https://public.example/file"),
    )
    with pytest.raises(url_snapshot.UrlSnapshotUnsupportedError):
        url_snapshot.fetch_public_html("https://public.example/file")


def test_redirects_are_revalidated_before_connecting_to_the_next_host(monkeypatch):
    connected = []

    class RedirectResponse:
        status = 302

        @staticmethod
        def getheader(name):
            return "http://127.0.0.1/admin" if name == "Location" else None

        @staticmethod
        def close():
            pass

    class RedirectConnection:
        def __init__(self, host, address, port, timeout):
            connected.append((host, address, port))

        @staticmethod
        def request(*args, **kwargs):
            pass

        @staticmethod
        def getresponse():
            return RedirectResponse()

        @staticmethod
        def close():
            pass

    def validate(url, timeout):
        assert timeout > 0
        if url.startswith("https://public.example/"):
            return "https", 443, "public.example", "93.184.216.34"
        raise UrlSnapshotError

    monkeypatch.setattr(url_snapshot, "_validate_and_resolve", validate)
    monkeypatch.setattr(url_snapshot, "_PinnedHTTPSConnection", RedirectConnection)
    with pytest.raises(UrlSnapshotError):
        url_snapshot._get(
            "https://public.example/start", url_snapshot.time.monotonic() + 10, 1000
        )
    assert connected == [("public.example", "93.184.216.34", 443)]
