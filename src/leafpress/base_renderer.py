"""Base renderer protocol and shared utilities for all output formats."""

from __future__ import annotations

import base64
import functools
import gzip
import mimetypes
import re
import stat
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Protocol

from leafpress.asset_policy import AssetPolicy, file_uri_to_path
from leafpress.config import BrandingConfig
from leafpress.git_info import GitVersion
from leafpress.mkdocs_parser import MkDocsConfig, NavItem


class BaseRenderer(Protocol):
    """Contract that every output-format renderer must satisfy."""

    def __init__(
        self,
        branding: BrandingConfig | None,
        git_info: GitVersion | None,
        mkdocs_cfg: MkDocsConfig,
        asset_policy: AssetPolicy | None = None,
    ) -> None: ...

    def render(
        self,
        html_pages: list[tuple[NavItem, str]],
        output_path: Path,
        cover_page: bool = True,
        include_toc: bool = True,
        local_time: bool = False,
    ) -> None: ...


# ---------------------------------------------------------------------------
# Shared helper functions used by multiple renderers
# ---------------------------------------------------------------------------


# A task-list checkbox, optionally wrapped in Material's custom_checkbox markup.
# Matches any attribute order/serialization (``checked``, ``checked=""``,
# ``checked/>``) so it still works after HTML sanitizing re-serializes tags.
_CHECKBOX_PATTERN = re.compile(
    r'(?:<label class="task-list-control">\s*)?'
    r"<input\b(?P<attrs>[^>]*\btype=[\"']?checkbox\b[^>]*?)/?>"
    r'(?:\s*<span class="task-list-indicator"></span>\s*</label>)?\s*',
    re.IGNORECASE,
)
_CHECKED_ATTR_PATTERN = re.compile(r"\bchecked\b", re.IGNORECASE)


def replace_checkboxes(html: str) -> str:
    """Replace task-list ``<input type="checkbox">`` elements with unicode symbols.

    WeasyPrint and static HTML don't render HTML form inputs, so we swap
    them for print-friendly ☑ / ☐ symbols. Handles both plain
    ``pymdownx.tasklist`` output and ``custom_checkbox: true`` output.
    """

    def _symbol(match: re.Match[str]) -> str:
        # Strip the type="checkbox" value before looking for "checked"
        attrs = re.sub(r"\btype=[\"']?checkbox[\"']?", "", match.group("attrs"))
        if _CHECKED_ATTR_PATTERN.search(attrs):
            return '<span class="task-checkbox checked">&#x2611;</span> '
        return '<span class="task-checkbox">&#x2610;</span> '

    return _CHECKBOX_PATTERN.sub(_symbol, html)


def make_anchor_id(title: str) -> str:
    """Convert a title to a URL-safe anchor ID."""
    slug = re.sub(r"[^\w\s-]", "", title.lower())
    return re.sub(r"[\s]+", "-", slug).strip("-")


def resolve_logo_uri(branding: BrandingConfig | None) -> str:
    """Get a URI for the logo (http(s):// or file://), or empty string."""
    if branding and branding.logo_path:
        logo = branding.logo_path
        if logo.startswith(("http://", "https://")):
            return logo
        return Path(logo).resolve().as_uri()
    return ""


_SVG_SUFFIXES = {".svg", ".svgz"}
# SVGs can start with a long XML prolog, DOCTYPE, or license comment
_SVG_SNIFF_BYTES = 1024 * 1024


def is_image_file(path: Path) -> bool:
    """True if ``path`` is an existing image file, judged by content rather than name.

    Raster images are anything Pillow can open and verify (PNG, JPEG, GIF,
    WebP, TIFF, ICO, ... with or without an extension); SVGs are ``.svg`` /
    ``.svgz`` files containing an ``<svg`` element. Results are cached per
    (path, modification time, size), since every renderer asks about the
    same files.
    """
    try:
        resolved = path.resolve()
        info = resolved.stat()
    except (OSError, RuntimeError):
        return False
    if not stat.S_ISREG(info.st_mode):
        return False
    return _is_image_cached(str(resolved), info.st_mtime_ns, info.st_size)


@functools.lru_cache(maxsize=2048)
def _is_image_cached(path_str: str, mtime_ns: int, size: int) -> bool:
    path = Path(path_str)
    suffix = path.suffix.lower()
    if suffix in _SVG_SUFFIXES:
        try:
            if suffix == ".svgz":
                with gzip.open(path, "rb") as f:
                    head = f.read(_SVG_SNIFF_BYTES)
            else:
                with path.open("rb") as f:
                    head = f.read(_SVG_SNIFF_BYTES)
        except (OSError, EOFError):
            return False
        return b"<svg" in head.lower()

    from PIL import Image

    try:
        with Image.open(path) as img:
            img.verify()
    except Exception:
        # Not an image, corrupt, or a decompression bomb (DecompressionBombError
        # subclasses Exception directly): never treat it as embeddable.
        return False
    return True


def build_asset_policy(
    mkdocs_cfg: MkDocsConfig,
    branding: BrandingConfig | None,
    extra_roots: Iterable[Path] = (),
) -> AssetPolicy:
    """Build the default local-file allowlist for rendering a project.

    Allows the mkdocs project directory, its docs_dir, any ``extra_roots``
    (e.g. the mermaid image temp dir or monorepo project dirs), and the
    configured logo file.
    """
    files: list[Path] = []
    if (
        branding
        and branding.logo_path
        and not branding.logo_path.startswith(("http://", "https://"))
        and is_image_file(Path(branding.logo_path))
    ):
        # Only a real image is allowlisted, so logo_path can't smuggle an
        # arbitrary file (a key, /proc/self/environ) into the output.
        files.append(Path(branding.logo_path))
    roots = [mkdocs_cfg.config_path.parent, mkdocs_cfg.docs_dir, *extra_roots]
    return AssetPolicy(roots, files)


_LOCAL_IMG_SRC_PATTERN = re.compile(r"""(<img\b[^>]*?\bsrc=)(["'])(file:[^"']*)\2""", re.IGNORECASE)


def rewrite_local_images(
    html: str, policy: AssetPolicy, replace: Callable[[Path], str | None]
) -> str:
    """Rewrite ``<img src="file://...">`` references for portable output formats.

    Local ``file://`` links only work on the machine that built the document
    (and mermaid images live in a temp dir that is deleted afterwards), so
    HTML and EPUB output must embed them. Paths outside ``policy`` are blanked.

    Args:
        html: Rendered HTML.
        policy: Which local files may be embedded.
        replace: Called with each allowed, existing image path; returns the new
            ``src`` value, or None to leave the reference unchanged.

    Example:
        >>> rewrite_local_images(html, policy, image_data_uri)
    """

    def _sub(match: re.Match[str]) -> str:
        prefix, quote, uri = match.groups()
        path = file_uri_to_path(uri)
        if path is None or not policy.allows(path):
            return f"{prefix}{quote}{quote}"
        if not path.is_file():
            return match.group(0)
        if not is_image_file(path):
            # Only real images are embedded: an <img> pointing at .env or a
            # key inside the project must not be base64'd into the output.
            return f"{prefix}{quote}{quote}"
        new_src = replace(path)
        return match.group(0) if new_src is None else f"{prefix}{quote}{new_src}{quote}"

    return _LOCAL_IMG_SRC_PATTERN.sub(_sub, html)


def image_mime_type(path: Path) -> str:
    """Guess an image MIME type from a file extension (default ``image/png``)."""
    return mimetypes.guess_type(path.name)[0] or "image/png"


def image_data_uri(path: Path) -> str:
    """Encode a local image as a ``data:`` URI for self-contained HTML."""
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{image_mime_type(path)};base64,{encoded}"
