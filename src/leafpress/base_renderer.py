"""Base renderer protocol and shared utilities for all output formats."""

from __future__ import annotations

import base64
import mimetypes
import re
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


def replace_checkboxes(html: str) -> str:
    """Replace <input type="checkbox"> elements with unicode symbols.

    WeasyPrint and static HTML don't render HTML form inputs, so we swap
    them for print-friendly unicode check/uncheck symbols.
    """
    # Checked: ☑
    html = re.sub(
        r'<label class="task-list-control">'
        r'<input type="checkbox" disabled checked/>'
        r'<span class="task-list-indicator"></span>'
        r"</label>\s*",
        '<span class="task-checkbox checked">&#x2611;</span> ',
        html,
    )
    # Unchecked: ☐
    html = re.sub(
        r'<label class="task-list-control">'
        r'<input type="checkbox" disabled/>'
        r'<span class="task-list-indicator"></span>'
        r"</label>\s*",
        '<span class="task-checkbox">&#x2610;</span> ',
        html,
    )
    return html


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
    ):
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
