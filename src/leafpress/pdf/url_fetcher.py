"""Restricted WeasyPrint URL fetcher.

WeasyPrint's default fetcher will load any ``file://`` path and any http(s)
URL referenced by the document, including via raw HTML such as
``<a rel="attachment" href="file:///proc/self/environ">``, which embeds the
file into the PDF. This fetcher only allows:

- ``data:`` URIs,
- ``file://`` paths permitted by the :class:`~leafpress.asset_policy.AssetPolicy`,
- ``http(s)://`` URLs whose host resolves to a public address, re-checked on
  every redirect hop, with a response size cap.
"""

from __future__ import annotations

import logging
from io import BytesIO
from urllib.error import HTTPError
from urllib.parse import urljoin, urlsplit

from weasyprint.urls import URLFetcher, URLFetcherResponse

from leafpress.asset_policy import AssetPolicy, is_public_http_url

logger = logging.getLogger(__name__)

MAX_RESPONSE_BYTES = 50 * 1024 * 1024
MAX_REDIRECTS = 5
_REDIRECT_CODES = {301, 302, 303, 307, 308}


class RestrictedURLFetcher(URLFetcher):
    """URL fetcher that confines file access and blocks internal hosts."""

    def __init__(self, policy: AssetPolicy, **kwargs: object) -> None:
        # Redirects are followed manually so each hop can be validated.
        super().__init__(allow_redirects=False, **kwargs)  # type: ignore[arg-type]
        self._policy = policy

    def fetch(self, url: str, headers: dict[str, str] | None = None) -> URLFetcherResponse:
        """Fetch ``url`` if policy allows it, otherwise raise ValueError.

        WeasyPrint catches the error, logs a warning, and skips the resource.
        """
        scheme = urlsplit(url).scheme.lower()
        if scheme == "data":
            return super().fetch(url, headers)
        if scheme == "file":
            if not self._policy.allows_uri(url):
                raise ValueError(f"Blocked local file outside the project: {url}")
            return super().fetch(url, headers)
        if scheme in ("http", "https"):
            return self._fetch_http(url, headers)
        raise ValueError(f"Blocked URL scheme {scheme!r}: {url}")

    def _fetch_http(self, url: str, headers: dict[str, str] | None) -> URLFetcherResponse:
        for _ in range(MAX_REDIRECTS + 1):
            if not is_public_http_url(url):
                raise ValueError(f"Blocked request to non-public host: {url}")
            try:
                response = super().fetch(url, headers)
            except HTTPError as exc:
                location = exc.headers.get("Location") if exc.headers else None
                if exc.code in _REDIRECT_CODES and location:
                    url = urljoin(url, location)
                    continue
                raise
            return self._capped(response)
        raise ValueError(f"Too many redirects: {url}")

    @staticmethod
    def _capped(response: URLFetcherResponse) -> URLFetcherResponse:
        """Read the body into memory, refusing anything over MAX_RESPONSE_BYTES."""
        try:
            body = response.read(MAX_RESPONSE_BYTES + 1)
        finally:
            response.close()
        if len(body) > MAX_RESPONSE_BYTES:
            raise ValueError(f"Response too large (> {MAX_RESPONSE_BYTES} bytes): {response.url}")
        return URLFetcherResponse(response.url, BytesIO(body), response.headers, response.status)
