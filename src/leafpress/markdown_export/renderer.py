"""Consolidated Markdown export — combines all pages into a single .md file."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from leafpress.config import BrandingConfig
from leafpress.git_info import GitVersion
from leafpress.mkdocs_parser import MkDocsConfig, NavItem


class MarkdownExportRenderer:
    """Generates a single Markdown file from all pages in an MkDocs project."""

    def __init__(
        self,
        branding: BrandingConfig | None,
        git_info: GitVersion | None,
        mkdocs_cfg: MkDocsConfig,
    ) -> None:
        self._branding = branding
        self._git_info = git_info
        self._mkdocs_cfg = mkdocs_cfg

    def render(
        self,
        html_pages: list[tuple[NavItem, str]],
        output_path: Path,
        cover_page: bool = True,
        include_toc: bool = True,
        local_time: bool = False,
    ) -> None:
        """Combine all source Markdown pages into a single document."""
        parts: list[str] = []

        if cover_page:
            parts.append(self._build_front_matter(local_time))

        if include_toc:
            parts.append(self._build_toc(html_pages))

        for item, _html in html_pages:
            if item.path is None:
                # Section divider — render as a heading
                if item.title:
                    level = min(item.level + 1, 6)
                    parts.append(f"{'#' * level} {item.title}")
                continue

            md_file = self._mkdocs_cfg.docs_dir / item.path
            if not md_file.exists():
                continue

            content = md_file.read_text(encoding="utf-8").strip()
            if content:
                parts.append(content)

        # Join with horizontal rules between sections
        output = "\n\n---\n\n".join(parts)

        # Ensure trailing newline
        if not output.endswith("\n"):
            output += "\n"

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output, encoding="utf-8")

    def _build_front_matter(self, local_time: bool) -> str:
        """Build YAML front matter with document metadata."""
        now = datetime.now() if local_time else datetime.now(timezone.utc)
        b = self._branding

        lines = ["---"]
        lines.append(f"title: \"{b.project_name if b else self._mkdocs_cfg.site_name}\"")
        if b and b.company_name:
            lines.append(f"company: \"{b.company_name}\"")
        if b and b.subtitle:
            lines.append(f"subtitle: \"{b.subtitle}\"")
        if b and b.author:
            lines.append(f"author: \"{b.author}\"")
        if b and b.document_owner:
            lines.append(f"document_owner: \"{b.document_owner}\"")
        if b and b.review_cycle:
            lines.append(f"review_cycle: \"{b.review_cycle}\"")
        lines.append(f"date: \"{now.strftime('%Y-%m-%d')}\"")
        if self._git_info:
            lines.append(f"version: \"{self._git_info.format_version_string()}\"")
        lines.append("---")
        return "\n".join(lines)

    @staticmethod
    def _build_toc(html_pages: list[tuple[NavItem, str]]) -> str:
        """Build a Markdown table of contents from the nav structure."""
        lines = ["## Table of Contents", ""]
        for item, _html in html_pages:
            if not item.title:
                continue
            indent = "  " * item.level
            slug = re.sub(r"[^\w\s-]", "", item.title.lower())
            slug = re.sub(r"[\s]+", "-", slug).strip("-")
            lines.append(f"{indent}- [{item.title}](#{slug})")
        return "\n".join(lines)
