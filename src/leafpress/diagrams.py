"""Fetch diagrams from external sources (URLs, Lucidchart API)."""

from __future__ import annotations

import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from rich.console import Console

from leafpress.asset_policy import is_within
from leafpress.config import DiagramsConfig, DiagramSource
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


MAX_PARALLEL_FETCHES = 4


def fetch_diagrams(
    config: DiagramsConfig,
    base_dir: Path,
    refresh: bool = False,
    console: Console | None = None,
) -> list[Path]:
    """Fetch all configured diagram sources concurrently.

    All destinations are validated (and the Lucidchart token resolved) before
    any request is made. Downloads then run in parallel; if any fail, the rest
    still complete and a single DiagramError lists every failure.

    Returns:
        Paths of cached and freshly downloaded diagrams, in config order.
    """
    if not config.sources:
        return []

    console = console or Console()
    token: str | None = None
    seen_dests: dict[Path, str] = {}
    # (index in config order, source, dest) for each entry that needs a fetch
    pending: list[tuple[int, DiagramSource, Path]] = []
    results: dict[int, Path] = {}

    for index, source in enumerate(config.sources):
        dest = base_dir / source.dest
        # dest comes from leafpress.yml; don't let it write outside the project
        # (e.g. dest: ../../.bashrc or an absolute path).
        if not is_within(dest, base_dir):
            raise DiagramError(
                f"Diagram dest must be inside the project directory ({base_dir}): {source.dest}"
            )
        resolved = dest.resolve()
        if resolved in seen_dests:
            raise DiagramError(
                f"Two diagram sources write to the same dest: {source.dest} "
                f"(also used by {seen_dests[resolved]})"
            )
        seen_dests[resolved] = source.dest

        if not source.url and not source.lucidchart:
            console.print(
                f"  [yellow]Skipping[/yellow] {source.dest}: no 'url' or 'lucidchart' specified"
            )
            continue

        if not refresh and not _is_stale(dest, config.cache_max_age):
            console.print(f"  [dim]Cached[/dim]   {source.dest}")
            results[index] = dest
            continue

        if source.lucidchart and not source.url and token is None:
            token = _resolve_lucidchart_token(config)
        pending.append((index, source, dest))

    def _fetch_one(source: DiagramSource, dest: Path) -> Path:
        if source.url:
            fetch_url(source.url, dest)
        else:
            if source.lucidchart is None or token is None:  # guaranteed by the loop above
                raise DiagramError(f"Lucidchart source missing document ID or token: {source.dest}")
            fetch_lucidchart(source.lucidchart, dest, token, source.page)
        return dest

    failures: list[str] = []
    if pending:
        workers = min(MAX_PARALLEL_FETCHES, len(pending))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {}
            for index, source, dest in pending:
                verb = "Fetching" if source.url else "Exporting"
                console.print(f"  [cyan]{verb}[/cyan] {source.dest}")
                futures[pool.submit(_fetch_one, source, dest)] = (index, source)
            for future in as_completed(futures):
                index, source = futures[future]
                try:
                    results[index] = future.result()
                except DiagramError as e:
                    console.print(f"  [red]Failed[/red]   {source.dest}: {e}")
                    failures.append(f"{source.dest}: {e}")

    if failures:
        raise DiagramError(
            f"{len(failures)} of {len(pending)} diagram download(s) failed:\n  "
            + "\n  ".join(failures)
        )
    return [results[i] for i in sorted(results)]
