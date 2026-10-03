"""Confine local file access and remote fetches made on behalf of document content.

Markdown sources, mkdocs.yml, and leafpress.yml may come from an untrusted
repository (a git URL source, a monorepo ``projects[].url`` entry, or a CI
checkout of a contributor's branch). Anything that turns a reference in that
content into a file read or network request goes through this module so that
content cannot pull arbitrary local files (``/etc/passwd``, ``~/.ssh``,
``/proc/self/environ``) or internal network endpoints (cloud metadata
services, localhost) into the generated documents.
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Iterable
from pathlib import Path
from urllib.parse import urlsplit


def file_uri_to_path(uri: str) -> Path | None:
    """Convert a ``file://`` URI to a local path, or None if it isn't one.

    Handles percent-encoding (``%20``) and strips query/fragment parts.
    """
    if not uri.startswith("file:"):
        return None
    try:
        return Path.from_uri(uri.split("?", 1)[0].split("#", 1)[0])
    except ValueError:
        return None


def is_within(path: Path, root: Path) -> bool:
    """Return True if ``path`` resolves (following symlinks) inside ``root``."""
    try:
        return path.resolve().is_relative_to(root.resolve())
    except (OSError, RuntimeError):
        return False


class AssetPolicy:
    """Allowlist of local directories and files that content may reference.

    Args:
        roots: Directories whose contents (recursively, after resolving
            symlinks) may be read.
        files: Individual files that may be read (e.g. a configured logo).
    """

    def __init__(self, roots: Iterable[Path], files: Iterable[Path] = ()) -> None:
        self._roots = [r.resolve() for r in roots]
        self._files = {f.resolve() for f in files}

    def add_root(self, root: Path) -> None:
        """Allow reads from another directory tree."""
        self._roots.append(root.resolve())

    def allows(self, path: Path) -> bool:
        """Return True if ``path`` may be read."""
        try:
            resolved = path.resolve()
        except (OSError, RuntimeError):
            return False
        if resolved in self._files:
            return True
        return any(resolved.is_relative_to(root) for root in self._roots)

    def allows_uri(self, uri: str) -> bool:
        """Return True if a ``file://`` URI points at an allowed path."""
        path = file_uri_to_path(uri)
        return path is not None and self.allows(path)


def is_public_host(host: str) -> bool:
    """Return True only if every address ``host`` resolves to is publicly routable.

    Blocks loopback, private (RFC 1918 / ULA), link-local (including the
    169.254.169.254 cloud metadata endpoint), multicast, reserved, and
    unspecified addresses. Unresolvable hosts are treated as not public.
    """
    if not host:
        return False
    try:
        infos = socket.getaddrinfo(host, None)
    except (OSError, UnicodeError):
        return False
    if not infos:
        return False
    for info in infos:
        addr = ipaddress.ip_address(str(info[4][0]).split("%", 1)[0])
        if not addr.is_global or addr.is_multicast:
            return False
    return True


def is_public_http_url(url: str) -> bool:
    """Return True if ``url`` is http(s) and its host is publicly routable."""
    parts = urlsplit(url)
    return parts.scheme in ("http", "https") and is_public_host(parts.hostname or "")
