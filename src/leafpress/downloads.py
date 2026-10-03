"""Bounded HTTP downloads.

Every place leafpress downloads something (diagrams, Lucidchart exports,
mermaid.ink renders, remote logos, ``import`` from a URL) goes through
:func:`download` so that responses are size-capped, only http(s) is used,
and redirects are re-validated hop by hop.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlsplit

import requests
from requests.structures import CaseInsensitiveDict

from leafpress.asset_policy import is_public_host

MAX_REDIRECTS = 5
_CHUNK_SIZE = 64 * 1024


class DownloadError(Exception):
    """A download was refused or failed."""


@dataclass(frozen=True)
class DownloadResult:
    """A completed download: body, response headers, and final URL after redirects."""

    body: bytes
    headers: CaseInsensitiveDict[str]
    url: str


# Credentials that must not follow a redirect to a different origin
_CREDENTIAL_HEADERS = {"authorization", "cookie", "proxy-authorization"}


def _origin(url: str) -> tuple[str, str, int | None]:
    parts = urlsplit(url)
    return parts.scheme, (parts.hostname or "").lower(), parts.port


def fetch(
    url: str,
    *,
    max_bytes: int,
    timeout: int = 30,
    headers: Mapping[str, str] | None = None,
    params: Mapping[str, Any] | None = None,
    require_public_host: bool = False,
) -> DownloadResult:
    """Download ``url`` into memory, following redirects safely.

    Args:
        url: http(s) URL to fetch.
        max_bytes: Refuse responses larger than this.
        timeout: Per-request timeout in seconds.
        headers: Extra request headers. Credentials (``Authorization``,
            ``Cookie``) are dropped if a redirect leads to another origin.
        params: Query parameters (first request only).
        require_public_host: Refuse hosts that resolve to loopback, private,
            or link-local addresses (e.g. cloud metadata). Use this for URLs
            that come from content or config you may not control.

    Raises:
        DownloadError: On a disallowed URL, HTTP error, network error, too
            many redirects, or a response over ``max_bytes``.

    Example:
        >>> fetch("https://example.com/logo.png", max_bytes=10_000_000).body  # doctest: +SKIP
    """
    request_headers = dict(headers or {})
    for _ in range(MAX_REDIRECTS + 1):
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https"):
            raise DownloadError(f"Only http(s) URLs are allowed: {url}")
        if require_public_host and not is_public_host(parts.hostname or ""):
            raise DownloadError(f"Refusing to fetch from a non-public host: {url}")
        try:
            resp = requests.get(
                url,
                stream=True,
                timeout=timeout,
                headers=request_headers,
                params=params,
                allow_redirects=False,
            )
        except requests.RequestException as e:
            raise DownloadError(f"Failed to download {url}: {e}") from e

        with resp:
            if resp.is_redirect:
                next_url = urljoin(url, resp.headers["Location"])
                # Redirects are followed here, not by requests, so its own
                # credential stripping doesn't apply: drop them ourselves when
                # the origin changes (including an https -> http downgrade).
                if _origin(next_url) != _origin(url):
                    request_headers = {
                        k: v
                        for k, v in request_headers.items()
                        if k.lower() not in _CREDENTIAL_HEADERS
                    }
                url = next_url
                params = None  # already baked into the Location URL
                continue
            try:
                resp.raise_for_status()
            except requests.HTTPError as e:
                raise DownloadError(f"Failed to download {url}: {e}") from e
            return DownloadResult(_read_capped(resp, url, max_bytes), resp.headers, url)
    raise DownloadError(f"Too many redirects: {url}")


def download(
    url: str,
    *,
    max_bytes: int,
    timeout: int = 30,
    headers: Mapping[str, str] | None = None,
    params: Mapping[str, Any] | None = None,
    require_public_host: bool = False,
) -> tuple[bytes, CaseInsensitiveDict[str]]:
    """Like :func:`fetch`, returning just ``(body, response_headers)``.

    Example:
        >>> body, hdrs = download("https://example.com/logo.png", max_bytes=10_000_000)
    """
    result = fetch(
        url,
        max_bytes=max_bytes,
        timeout=timeout,
        headers=headers,
        params=params,
        require_public_host=require_public_host,
    )
    return result.body, result.headers


def _read_capped(resp: requests.Response, url: str, max_bytes: int) -> bytes:
    declared = resp.headers.get("Content-Length")
    if declared and declared.isdigit() and int(declared) > max_bytes:
        raise DownloadError(f"Response too large ({declared} bytes > {max_bytes}): {url}")
    chunks: list[bytes] = []
    total = 0
    try:
        for chunk in resp.iter_content(chunk_size=_CHUNK_SIZE):
            total += len(chunk)
            if total > max_bytes:
                raise DownloadError(f"Response too large (> {max_bytes} bytes): {url}")
            chunks.append(chunk)
    except requests.RequestException as e:
        raise DownloadError(f"Failed to download {url}: {e}") from e
    return b"".join(chunks)
