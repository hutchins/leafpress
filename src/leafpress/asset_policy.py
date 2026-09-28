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
    unspecified addresses, including when reached through NAT64 or other
    IPv4-in-IPv6 forms. Unresolvable hosts are treated as not public.

    Known limitation: the name is resolved again when the connection is made,
    so a DNS-rebinding host (public on the first lookup, internal on the
    second) can still get through. Treat this as a strong guard for honest
    misconfiguration and common SSRF payloads, not as a network firewall.
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
        addr = _embedded_ipv4(ipaddress.ip_address(str(info[4][0]).split("%", 1)[0]))
        if not addr.is_global or addr.is_multicast:
            return False
    return True


_NAT64_PREFIX = ipaddress.IPv6Network("64:ff9b::/96")


def _embedded_ipv4(
    addr: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    """Return the IPv4 address an IPv6 address tunnels to, if any.

    ``64:ff9b::7f00:1`` (NAT64) reaches 127.0.0.1 but Python reports it as
    global, so IPv4-mapped, NAT64, 6to4, and Teredo addresses are checked by
    the IPv4 address they carry.
    """
    if isinstance(addr, ipaddress.IPv4Address):
        return addr
    if addr.ipv4_mapped is not None:
        return addr.ipv4_mapped
    if addr in _NAT64_PREFIX:
        return ipaddress.IPv4Address(int(addr) & 0xFFFFFFFF)
    if addr.sixtofour is not None:
        return addr.sixtofour
    if addr.teredo is not None:
        return addr.teredo[1]
    return addr


def is_public_http_url(url: str) -> bool:
    """Return True if ``url`` is http(s) and its host is publicly routable."""
    parts = urlsplit(url)
    return parts.scheme in ("http", "https") and is_public_host(parts.hostname or "")
