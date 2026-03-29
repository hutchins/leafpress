"""Base renderer protocol and shared utilities for all output formats."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Protocol

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
