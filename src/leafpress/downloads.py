"""Bounded HTTP downloads.

Every place leafpress downloads something (diagrams, Lucidchart exports,
mermaid.ink renders, remote logos, ``import`` from a URL) goes through
:func:`download` so that responses are size-capped, only http(s) is used,
and redirects are re-validated hop by hop.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urljoin, urlsplit

import requests
from requests.structures import CaseInsensitiveDict

from leafpress.asset_policy import is_public_host

MAX_REDIRECTS = 5
_CHUNK_SIZE = 64 * 1024


class DownloadError(Exception):
    """A download was refused or failed."""


def download(
    url: str,
    *,
    max_bytes: int,
    timeout: int = 30,
    headers: Mapping[str, str] | None = None,
    params: Mapping[str, Any] | None = None,
    require_public_host: bool = False,
) -> tuple[bytes, CaseInsensitiveDict[str]]:
    """Download ``url`` into memory and return ``(body, response_headers)``.

    Args:
        url: http(s) URL to fetch.
        max_bytes: Refuse responses larger than this.
        timeout: Per-request timeout in seconds.
        headers: Extra request headers.
        params: Query parameters.
        require_public_host: Refuse hosts that resolve to loopback, private,
            or link-local addresses (e.g. cloud metadata). Use this for URLs
            that come from content or config you may not control.

    Raises:
        DownloadError: On a disallowed URL, HTTP error, network error, too
            many redirects, or a response over ``max_bytes``.

    Example:
        >>> body, hdrs = download("https://example.com/logo.png", max_bytes=10_000_000)
    """
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
                headers=dict(headers or {}),
                params=params,
                allow_redirects=False,
            )
        except requests.RequestException as e:
            raise DownloadError(f"Failed to download {url}: {e}") from e

        with resp:
            if resp.is_redirect:
                # requests drops Authorization on cross-host redirects itself;
                # query params are already baked into the Location URL.
                url = urljoin(url, resp.headers["Location"])
                params = None
                continue
            try:
                resp.raise_for_status()
            except requests.HTTPError as e:
                raise DownloadError(f"Failed to download {url}: {e}") from e
            return _read_capped(resp, url, max_bytes), resp.headers
    raise DownloadError(f"Too many redirects: {url}")


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
