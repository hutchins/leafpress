"""Fetch diagrams from external sources (URLs, Lucidchart API)."""

from __future__ import annotations

import os
import time
from pathlib import Path

import requests
from rich.console import Console

from leafpress.config import DiagramsConfig
from leafpress.exceptions import DiagramError

_LUCIDCHART_API_BASE = "https://api.lucid.co/documents"


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
    """Download a file from an HTTP/HTTPS URL."""
    try:
        resp = requests.get(url, stream=True, timeout=timeout)
        resp.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        return dest
    except requests.RequestException as e:
        raise DiagramError(f"Failed to download {url}: {e}") from e


def fetch_lucidchart(
    document_id: str,
    dest: Path,
    token: str,
    page: int = 1,
    timeout: int = 30,
) -> Path:
    """Export a diagram from Lucidchart as PNG via the REST API."""
    url = f"{_LUCIDCHART_API_BASE}/{document_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "image/png",
    }
    params = {"pageIndex": page - 1, "crop": "true"}

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=timeout)
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "")
        if "image" not in content_type:
            raise DiagramError(
                f"Lucidchart returned unexpected content type '{content_type}' "
                f"for document {document_id}"
            )

        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            f.write(resp.content)
        return dest
    except requests.RequestException as e:
        raise DiagramError(
            f"Failed to export Lucidchart document {document_id}: {e}"
        ) from e


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
        dest = Path(source.dest)
        if not dest.is_absolute():
            dest = base_dir / dest

        if not source.url and not source.lucidchart:
            console.print(
                f"  [yellow]Skipping[/yellow] {source.dest}: "
                "no 'url' or 'lucidchart' specified"
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
