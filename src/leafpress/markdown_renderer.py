"""Markdown to HTML conversion with MkDocs-compatible extensions."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import markdown

logger = logging.getLogger(__name__)

# Extensions that are always enabled
BASELINE_EXTENSIONS = ["meta", "toc", "tables"]

# Common Material/MkDocs icon shortcodes mapped to unicode equivalents
_MATERIAL_ICON_MAP: dict[str, str] = {
    ":material-download:": "\u2b07",  # ⬇
    ":material-upload:": "\u2b06",  # ⬆
    ":material-dns-outline:": "\U0001f5a7",  # 🖧
    ":material-check:": "\u2714",  # ✔
    ":material-close:": "\u2716",  # ✖
    ":material-alert:": "\u26a0",  # ⚠
    ":material-information:": "\u2139",
    ":material-star:": "\u2b50",  # ⭐
    ":material-heart:": "\u2764",  # ❤
    ":material-link:": "\U0001f517",  # 🔗
    ":material-file:": "\U0001f4c4",  # 📄
    ":material-folder:": "\U0001f4c1",  # 📁
    ":material-cog:": "\u2699",  # ⚙
    ":material-lock:": "\U0001f512",  # 🔒
    ":material-eye:": "\U0001f441",  # 👁
    ":material-pencil:": "\u270f",  # ✏
    ":material-delete:": "\U0001f5d1",  # 🗑
    ":material-search:": "\U0001f50d",  # 🔍
    ":material-home:": "\U0001f3e0",  # 🏠
    ":material-email:": "\u2709",  # ✉
}

# Regex to match any remaining :shortcode: patterns (unresolved emoji)
_SHORTCODE_PATTERN = re.compile(r":[\w+-]+:")

# Known safe pymdown-extensions mappings
PYMDOWNX_EXTENSIONS = {
    "pymdownx.highlight",
    "pymdownx.inlinehilite",
    "pymdownx.superfences",
    "pymdownx.tabbed",
    "pymdownx.details",
    "pymdownx.tasklist",
    "pymdownx.emoji",
    "pymdownx.arithmatex",
    "pymdownx.critic",
    "pymdownx.caret",
    "pymdownx.keys",
    "pymdownx.mark",
    "pymdownx.tilde",
    "pymdownx.smartsymbols",
    "pymdownx.betterem",
    "pymdownx.magiclink",
    "pymdownx.snippets",
    "pymdownx.striphtml",
}


class MarkdownRenderer:
    """Converts Markdown content to HTML using MkDocs-compatible extensions."""

    def __init__(
        self,
        extensions: list[str | dict[str, Any]],
        docs_dir: Path,
        mermaid_output_dir: Path | None = None,
    ) -> None:
        self._docs_dir = docs_dir
        self._mermaid_output_dir = mermaid_output_dir
        self._extension_names: list[str] = []
        self._extension_configs: dict[str, dict[str, Any]] = {}
        self._parse_extensions(extensions)
        self._md = self._build_markdown_instance()

    def _parse_extensions(self, extensions: list[str | dict[str, Any]]) -> None:
        """Normalize mkdocs.yml extension list into names + configs."""
        seen: set[str] = set()

        for ext in extensions:
            if isinstance(ext, str):
                if ext not in seen:
                    self._extension_names.append(ext)
                    seen.add(ext)
            elif isinstance(ext, dict):
                for name, config in ext.items():
                    if name not in seen:
                        self._extension_names.append(name)
                        seen.add(name)
                    if isinstance(config, dict):
                        # Filter out !!python/name references that yaml.safe_load
                        # cannot resolve
                        clean_config = {
                            k: v
                            for k, v in config.items()
                            if not (isinstance(v, str) and v.startswith("!!python/"))
                        }
                        self._extension_configs[name] = clean_config

    def _build_markdown_instance(self) -> markdown.Markdown:
        """Create a configured Markdown instance."""
        all_extensions = list(BASELINE_EXTENSIONS)
        for ext in self._extension_names:
            if ext not in all_extensions:
                all_extensions.append(ext)

        # Try loading each extension; skip those that fail
        valid_extensions: list[str] = []
        for ext in all_extensions:
            try:
                markdown.Markdown(extensions=[ext])
                valid_extensions.append(ext)
            except Exception:
                logger.warning("Skipping unavailable extension: %s", ext)

        return markdown.Markdown(
            extensions=valid_extensions,
            extension_configs=self._extension_configs,
            output_format="html",
        )

    def render(self, md_content: str, source_path: Path) -> str:
        """Convert a single Markdown string to HTML.

        Args:
            md_content: Raw Markdown text.
            source_path: Path to the .md file (for resolving relative links/images).

        Returns:
            HTML string.
        """
        self._md.reset()
        html = self._md.convert(md_content)
        html = self._resolve_relative_assets(html, source_path)
        html = self._resolve_emoji_shortcodes(html)
        html = self._render_annotations(html)
        html = self._render_mermaid_blocks(html)
        return html

    def _resolve_relative_assets(self, html: str, source_path: Path) -> str:
        """Rewrite relative image src and link href to absolute file:// paths."""
        source_dir = source_path.parent

        def _rewrite_src(match: re.Match[str]) -> str:
            attr = match.group(1)  # src or href
            quote = match.group(2)
            path = match.group(3)

            # Skip absolute URLs and anchors
            if path.startswith(("http://", "https://", "file://", "#", "mailto:")):
                return match.group(0)

            resolved = (source_dir / path).resolve()
            if resolved.exists():
                return f"{attr}={quote}{resolved.as_uri()}{quote}"
            return match.group(0)

        # Match src="..." and href="..." (but not external URLs)
        html = re.sub(
            r'(src|href)=(["\'])((?!https?://|file://|#|mailto:)[^"\']+)\2',
            _rewrite_src,
            html,
        )
        return html

    def _resolve_emoji_shortcodes(self, html: str) -> str:
        """Replace unresolved :material-*: and other emoji shortcodes.

        Material for MkDocs uses pymdownx.emoji with custom handlers that
        require the material-extensions package. When those aren't available,
        shortcodes pass through as literal text. We replace known ones with
        unicode and strip unknown ones.
        """
        # Replace known shortcodes with unicode
        for shortcode, unicode_char in _MATERIAL_ICON_MAP.items():
            html = html.replace(shortcode, unicode_char)

        # Remove any remaining :material-*: or :fontawesome-*: shortcodes
        html = re.sub(r":(?:material|fontawesome|octicons)[\w-]+:", "", html)

        return html

    def _render_annotations(self, html: str) -> str:
        """Render Material for MkDocs annotation blocks as footnote-style references."""
        from leafpress.annotations import render_annotations

        return render_annotations(html)

    def _render_mermaid_blocks(self, html: str) -> str:
        """Render mermaid code blocks to PNG images."""
        if self._mermaid_output_dir is None:
            return html

        from leafpress.mermaid import render_mermaid_blocks

        return render_mermaid_blocks(html, self._mermaid_output_dir)
