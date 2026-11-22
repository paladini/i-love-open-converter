"""Fetch and inline a bounded public web page for the offline HTML renderer."""

from __future__ import annotations

import base64
import concurrent.futures
import http.client
import ipaddress
import re
import socket
import ssl
import time
from dataclasses import dataclass
from html import escape
from urllib.parse import urljoin, urlsplit, urlunsplit

from lxml import html

MAX_URL_PAGE_BYTES = 10 * 1024 * 1024
MAX_URL_RESOURCE_BYTES = 10 * 1024 * 1024
MAX_URL_TOTAL_BYTES = 50 * 1024 * 1024
MAX_URL_RESOURCES = 50
MAX_URL_REDIRECTS = 5
URL_FETCH_TIMEOUT_SECONDS = 30
_DNS_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=4, thread_name_prefix="url-dns"
)
_CSS_URL = re.compile(r"url\(\s*(?:([\"'])(.*?)\1|([^)]*?))\s*\)", re.IGNORECASE)
_CSS_IMPORT = re.compile(r"@import\s+(?:([\"'])(.*?)\1)([^;]*);", re.IGNORECASE)
_CSS_IMPORT_URL = re.compile(
    r"@import\s+url\(\s*(?:([\"'])(.*?)\1|([^)]*?))\s*\)([^;]*);", re.IGNORECASE
)
_ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp", "image/svg+xml"}
_ALLOWED_FONT_TYPES = {
    "font/woff",
    "font/woff2",
    "font/ttf",
    "font/otf",
    "application/font-woff",
    "application/vnd.ms-fontobject",
    "application/x-font-ttf",
    "application/x-font-opentype",
}


class UrlSnapshotError(Exception):
    """A public URL or one of its resources could not be fetched safely."""


class UrlSnapshotTooLargeError(UrlSnapshotError):
    """A URL snapshot exceeded a configured byte, resource, or time bound."""


class UrlSnapshotUnsupportedError(UrlSnapshotError):
    """The URL's main response is not an HTML document."""


@dataclass(frozen=True)
class _Response:
    body: bytes
    content_type: str
    final_url: str


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host: str, address: str, port: int, timeout: float) -> None:
        super().__init__(host, port, timeout=timeout)
        self._address = address

    def connect(self) -> None:
        self.sock = socket.create_connection((self._address, self.port), self.timeout)


class _PinnedHTTPSConnection(_PinnedHTTPConnection):
    default_port = 443

    def connect(self) -> None:
        raw = socket.create_connection((self._address, self.port), self.timeout)
        try:
            self.sock = ssl.create_default_context().wrap_socket(raw, server_hostname=self.host)
        except Exception:
            raw.close()
            raise


def _validate_and_resolve(url: str, timeout: float = 5.0) -> tuple[str, int, str, str]:
    if (
        not isinstance(url, str)
        or not url
        or len(url) > 4096
        or any(ord(char) < 32 for char in url)
    ):
        raise UrlSnapshotError
    try:
        parsed = urlsplit(url)
        scheme = parsed.scheme.lower()
        host = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise UrlSnapshotError from exc
    if (
        scheme not in {"http", "https"}
        or not host
        or parsed.username is not None
        or parsed.password is not None
        or "\\" in parsed.netloc
    ):
        raise UrlSnapshotError
    expected_port = 80 if scheme == "http" else 443
    if port not in (None, expected_port):
        raise UrlSnapshotError
    try:
        literal = ipaddress.ip_address(host)
        addresses = [str(literal)]
    except ValueError:
        try:
            lookup = _DNS_EXECUTOR.submit(
                socket.getaddrinfo,
                host.encode("idna").decode("ascii"),
                expected_port,
                0,
                socket.SOCK_STREAM,
            )
            resolved = lookup.result(timeout=max(0.1, timeout))
            addresses = list(dict.fromkeys(entry[4][0] for entry in resolved))
        except concurrent.futures.TimeoutError as exc:
            raise UrlSnapshotTooLargeError from exc
        except (OSError, UnicodeError) as exc:
            raise UrlSnapshotError from exc
    if not addresses:
        raise UrlSnapshotError
    try:
        parsed_addresses = [ipaddress.ip_address(address) for address in addresses]
    except ValueError as exc:
        raise UrlSnapshotError from exc
    if any(not address.is_global for address in parsed_addresses):
        raise UrlSnapshotError
    # Connecting to the pinned address prevents DNS rebinding between validation and connect.
    connect_address = str(parsed_addresses[0])
    return scheme, expected_port, host.encode("idna").decode("ascii"), connect_address


def _get(url: str, deadline: float, byte_limit: int) -> _Response:
    current = url
    for redirect_count in range(MAX_URL_REDIRECTS + 1):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise UrlSnapshotTooLargeError
        scheme, port, host, address = _validate_and_resolve(current, remaining)
        parsed = urlsplit(current)
        connection_type = _PinnedHTTPSConnection if scheme == "https" else _PinnedHTTPConnection
        connection = connection_type(host, address, port, min(5.0, remaining))
        target = urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
        authority = f"[{host}]" if ":" in host else host
        try:
            connection.request(
                "GET",
                target,
                headers={
                    "Host": authority,
                    "User-Agent": "I-Love-Open-Converter/1.0 (+self-hosted URL conversion)",
                    "Accept": "text/html, text/css, image/*, font/*;q=0.8, */*;q=0.1",
                    "Accept-Encoding": "identity",
                    "Connection": "close",
                },
            )
            response = connection.getresponse()
            if response.status in {301, 302, 303, 307, 308}:
                location = response.getheader("Location")
                response.close()
                if not location or redirect_count >= MAX_URL_REDIRECTS:
                    raise UrlSnapshotError
                current = urljoin(current, location)
                continue
            if response.status != 200:
                raise UrlSnapshotError
            if response.getheader("Content-Encoding", "identity").lower() not in {"", "identity"}:
                raise UrlSnapshotError
            length = response.getheader("Content-Length")
            if length and int(length) > byte_limit:
                raise UrlSnapshotTooLargeError
            content_type = response.getheader("Content-Type", "application/octet-stream")
            body = bytearray()
            connection.sock.settimeout(min(5.0, max(0.1, deadline - time.monotonic())))
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise UrlSnapshotTooLargeError
                connection.sock.settimeout(min(5.0, remaining))
                chunk = response.read(min(64 * 1024, byte_limit + 1 - len(body)))
                if not chunk:
                    break
                body.extend(chunk)
                if len(body) > byte_limit or time.monotonic() > deadline:
                    raise UrlSnapshotTooLargeError
            return _Response(bytes(body), content_type.split(";", 1)[0].strip().lower(), current)
        except (OSError, ssl.SSLError, http.client.HTTPException, ValueError) as exc:
            raise UrlSnapshotError from exc
        finally:
            connection.close()
    raise UrlSnapshotError


def fetch_public_html(url: str) -> bytes:
    """Return a self-contained HTML snapshot; all network access ends before rendering."""
    deadline = time.monotonic() + URL_FETCH_TIMEOUT_SECONDS
    total_bytes = 0
    resources = 1
    cache: dict[str, tuple[str, bytes, str]] = {}
    css_stack: set[str] = set()

    def resource_data(raw_url: str, *, stylesheet: bool = False, depth: int = 0) -> str:
        nonlocal total_bytes, resources
        raw_url = raw_url.strip()
        if raw_url.startswith("#") or raw_url.lower().startswith("data:"):
            return raw_url
        absolute = urljoin(base_url[0], raw_url)
        if absolute in cache:
            mime, body, _ = cache[absolute]
            return f"data:{mime};base64,{base64.b64encode(body).decode('ascii')}"
        resources += 1
        if resources > MAX_URL_RESOURCES or depth > 4:
            raise UrlSnapshotTooLargeError
        response = _get(absolute, deadline, MAX_URL_RESOURCE_BYTES)
        total_bytes += len(response.body)
        if total_bytes > MAX_URL_TOTAL_BYTES:
            raise UrlSnapshotTooLargeError
        mime = response.content_type
        if stylesheet:
            if mime not in {"text/css", "application/css"}:
                raise UrlSnapshotError
            css_stack.add(absolute)
            body = _inline_css(
                response.body.decode("utf-8", "replace"), response.final_url, depth + 1
            )
            css_stack.discard(absolute)
            encoded = base64.b64encode(body.encode("utf-8")).decode("ascii")
            result = f"data:text/css;charset=utf-8;base64,{encoded}"
            cache[absolute] = ("text/css", body.encode("utf-8"), response.final_url)
            return result
        if mime not in _ALLOWED_IMAGE_TYPES | _ALLOWED_FONT_TYPES:
            raise UrlSnapshotError
        cache[absolute] = (mime, response.body, response.final_url)
        return f"data:{mime};base64,{base64.b64encode(response.body).decode('ascii')}"

    def _inline_css(css_text: str, css_url: str, depth: int) -> str:
        previous_base = base_url[0]
        base_url[0] = css_url
        try:
            def import_replace(match: re.Match[str], target: str, suffix: str) -> str:
                resolved = urljoin(base_url[0], target)
                if resolved in css_stack:
                    return ""
                data_uri = resource_data(target, stylesheet=True, depth=depth)
                return f'@import url("{data_uri}"){suffix};'

            css_text = _CSS_IMPORT_URL.sub(
                lambda match: import_replace(
                    match,
                    match.group(2) if match.group(1) else match.group(3) or "",
                    match.group(4),
                ),
                css_text,
            )
            css_text = _CSS_IMPORT.sub(
                lambda match: import_replace(match, match.group(2), match.group(3)), css_text
            )

            def url_replace(match: re.Match[str]) -> str:
                target = (
                    match.group(2) if match.group(1) else match.group(3) or ""
                ).strip().strip("\"'")
                if not target or target.lower().startswith("data:") or target.startswith("#"):
                    return match.group(0)
                data_uri = resource_data(target, depth=depth)
                return f'url("{escape(data_uri, quote=True)}")'

            return _CSS_URL.sub(url_replace, css_text)
        finally:
            base_url[0] = previous_base

    if not isinstance(url, str):
        raise UrlSnapshotError
    response = _get(url, deadline, MAX_URL_PAGE_BYTES)
    if time.monotonic() > deadline:
        raise UrlSnapshotTooLargeError
    if response.content_type not in {"text/html", "application/xhtml+xml"}:
        raise UrlSnapshotUnsupportedError
    total_bytes += len(response.body)
    base_url = [response.final_url]
    try:
        document = html.fromstring(response.body, base_url=response.final_url)
    except (ValueError, TypeError) as exc:
        raise UrlSnapshotError from exc
    for node in list(document.xpath("//script|//iframe|//object|//embed|//applet|//video|//audio")):
        parent = node.getparent()
        if parent is not None:
            parent.remove(node)
    refresh_or_base = "//meta[translate(@http-equiv, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
    refresh_or_base += "'abcdefghijklmnopqrstuvwxyz')='refresh'] | //base"
    for node in list(document.xpath(refresh_or_base)):
        parent = node.getparent()
        if parent is not None:
            parent.remove(node)
    for node in document.iter():
        for attribute in list(node.attrib):
            if attribute.lower().startswith("on") or attribute.lower() == "srcset":
                del node.attrib[attribute]
        if node.tag.lower() == "link" and "stylesheet" in node.get("rel", "").lower().split():
            href = node.get("href")
            if href:
                node.set("href", resource_data(href, stylesheet=True))
        for attribute in ("src", "poster"):
            target = node.get(attribute)
            if target and not target.lower().startswith("data:"):
                node.set(attribute, resource_data(target))
        style = node.get("style")
        if style:
            node.set("style", _inline_css(style, response.final_url, 0))
        if node.tag.lower() == "style" and node.text:
            node.text = _inline_css(node.text, response.final_url, 0)
    serialized = html.tostring(document, encoding="utf-8", doctype="<!doctype html>")
    if len(serialized) > MAX_URL_TOTAL_BYTES:
        raise UrlSnapshotTooLargeError
    return serialized
