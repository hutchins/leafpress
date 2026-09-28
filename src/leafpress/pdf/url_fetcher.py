"""Restricted WeasyPrint URL fetcher.

WeasyPrint's default fetcher will load any ``file://`` path and any http(s)
URL referenced by the document, including via raw HTML such as
``<a rel="attachment" href="file:///proc/self/environ">``, which embeds the
file into the PDF. This fetcher only allows:

- ``data:`` URIs,
- ``file://`` images permitted by the :class:`~leafpress.asset_policy.AssetPolicy`,
- ``http(s)://`` URLs on public hosts, fetched through
  :func:`leafpress.downloads.fetch` (``requests``, redirects re-validated hop
  by hop, credentials never forwarded cross-origin, size-capped).
"""

from __future__ import annotations

from io import BytesIO
from urllib.parse import urlsplit

from weasyprint.urls import URLFetcher, URLFetcherResponse

from leafpress.asset_policy import AssetPolicy, file_uri_to_path
from leafpress.base_renderer import is_image_file
from leafpress.downloads import DownloadError, fetch

MAX_RESPONSE_BYTES = 50 * 1024 * 1024

# requests has already decoded the body, so these no longer describe it
_DROPPED_RESPONSE_HEADERS = {"content-encoding", "content-length", "transfer-encoding"}


class RestrictedURLFetcher(URLFetcher):
    """URL fetcher that confines file access and blocks internal hosts."""

    def __init__(self, policy: AssetPolicy, timeout: int = 30) -> None:
        super().__init__(timeout=timeout)
        self._policy = policy
        self._http_timeout = timeout

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
            path = file_uri_to_path(url)
            # leafpress only ever loads images from disk (content images, the
            # logo, mermaid PNGs); anything else, e.g. an rel="attachment"
            # link to the project's .env, is refused.
            if path is None or not is_image_file(path):
                raise ValueError(f"Blocked non-image local file: {url}")
            return super().fetch(url, headers)
        if scheme in ("http", "https"):
            return self._fetch_http(url, headers)
        raise ValueError(f"Blocked URL scheme {scheme!r}: {url}")

    def _fetch_http(self, url: str, headers: dict[str, str] | None) -> URLFetcherResponse:
        try:
            result = fetch(
                url,
                max_bytes=MAX_RESPONSE_BYTES,
                timeout=self._http_timeout,
                headers=headers,
                require_public_host=True,
            )
        except DownloadError as e:
            raise ValueError(str(e)) from e
        response_headers = {
            k: v for k, v in result.headers.items() if k.lower() not in _DROPPED_RESPONSE_HEADERS
        }
        return URLFetcherResponse(result.url, BytesIO(result.body), response_headers)
