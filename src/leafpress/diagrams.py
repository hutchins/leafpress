"""Fetch diagrams from external sources (URLs, Lucidchart API)."""

from __future__ import annotations

import os
import re
import time
from pathlib import Path

from rich.console import Console

from leafpress.asset_policy import is_within
from leafpress.config import DiagramsConfig
from leafpress.downloads import DownloadError, download
from leafpress.exceptions import DiagramError

_LUCIDCHART_API_BASE = "https://api.lucid.co/documents"
_LUCIDCHART_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
MAX_DIAGRAM_BYTES = 50 * 1024 * 1024


def _is_stale(dest: Path, max_age: int) -> bool:
    """Return True if the file needs to be (re-)downloaded."""
    if not dest.exists():
        return True
    if max_age == 0:
        return True
    age = time.time() - dest.stat().st_mtime
    return age > max_age


def _resolve_lucidchart_token(config: DiagramsConfig) -> str:
    """Get the Lucidchart API token from config or environment."""
    token = config.lucidchart_token or os.environ.get("LEAFPRESS_LUCIDCHART_TOKEN")
    if not token:
        raise DiagramError(
            "Lucidchart API token required. Set 'lucidchart_token' in config "
            "or the LEAFPRESS_LUCIDCHART_TOKEN environment variable."
        )
    return token


def fetch_url(url: str, dest: Path, timeout: int = 30) -> Path:
    """Download a file from an HTTP/HTTPS URL (capped at MAX_DIAGRAM_BYTES)."""
    try:
        body, _ = download(url, max_bytes=MAX_DIAGRAM_BYTES, timeout=timeout)
    except DownloadError as e:
        raise DiagramError(str(e)) from e
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(body)
    return dest


def fetch_lucidchart(
    document_id: str,
    dest: Path,
    token: str,
    page: int = 1,
    timeout: int = 30,
) -> Path:
    """Export a diagram from Lucidchart as PNG via the REST API."""
    # The ID goes into the URL path alongside the bearer token, so keep it to
    # a plain identifier (no "/", "..", or query characters).
    if not _LUCIDCHART_ID_PATTERN.match(document_id):
        raise DiagramError(f"Invalid Lucidchart document ID: {document_id!r}")
    url = f"{_LUCIDCHART_API_BASE}/{document_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "image/png",
    }
    params = {"pageIndex": page - 1, "crop": "true"}

    try:
        body, resp_headers = download(
            url,
            max_bytes=MAX_DIAGRAM_BYTES,
            timeout=timeout,
            headers=headers,
            params=params,
        )
    except DownloadError as e:
        raise DiagramError(f"Failed to export Lucidchart document {document_id}: {e}") from e

    content_type = resp_headers.get("Content-Type", "")
    if "image" not in content_type:
        raise DiagramError(
            f"Lucidchart returned unexpected content type '{content_type}' "
            f"for document {document_id}"
        )

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(body)
    return dest


def fetch_diagrams(
    config: DiagramsConfig,
    base_dir: Path,
    refresh: bool = False,
    console: Console | None = None,
) -> list[Path]:
    """Fetch all configured diagram sources. Returns list of downloaded paths."""
    if not config.sources:
        return []

    console = console or Console()
    downloaded: list[Path] = []
    token: str | None = None

    for source in config.sources:
        dest = base_dir / source.dest
        # dest comes from leafpress.yml; don't let it write outside the project
        # (e.g. dest: ../../.bashrc or an absolute path).
        if not is_within(dest, base_dir):
            raise DiagramError(
                f"Diagram dest must be inside the project directory ({base_dir}): {source.dest}"
            )

        if not source.url and not source.lucidchart:
            console.print(
                f"  [yellow]Skipping[/yellow] {source.dest}: no 'url' or 'lucidchart' specified"
            )
            continue

        if not refresh and not _is_stale(dest, config.cache_max_age):
            console.print(f"  [dim]Cached[/dim]   {source.dest}")
            downloaded.append(dest)
            continue

        if source.url:
            console.print(f"  [cyan]Fetching[/cyan] {source.dest}")
            fetch_url(source.url, dest)
        elif source.lucidchart:
            if token is None:
                token = _resolve_lucidchart_token(config)
            console.print(f"  [cyan]Exporting[/cyan] {source.dest}")
            fetch_lucidchart(source.lucidchart, dest, token, source.page)

        downloaded.append(dest)

    return downloaded
