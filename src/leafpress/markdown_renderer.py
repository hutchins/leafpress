"""Markdown to HTML conversion with MkDocs-compatible extensions."""

from __future__ import annotations

import importlib
import logging
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import markdown
from markupsafe import Markup

from leafpress.asset_policy import AssetPolicy

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


def _mermaid_fence_format(
    source: str,
    language: str,
    css_class: str,
    options: dict[str, Any],
    md: markdown.Markdown,
    **kwargs: Any,
) -> str:
    """Custom fence formatter that preserves mermaid class for later rendering."""
    return f'<pre class="mermaid"><code>{Markup.escape(source)}</code></pre>'


# Superfences config to route mermaid blocks through our custom formatter
_SUPERFENCES_CONFIG = {
    "custom_fences": [{"name": "mermaid", "class": "mermaid", "format": _mermaid_fence_format}]
}


def _is_extension_class_ref(ext: str) -> bool:
    """Check that a ``module:ClassName`` extension reference names an Extension.

    Python-Markdown instantiates ``module:ClassName`` references with the
    configured options as keyword arguments, so mkdocs.yml could otherwise make
    it construct arbitrary classes (e.g. ``subprocess:Popen``). Plain module
    names are loaded via their ``makeExtension`` factory and are left alone.
    """
    if ":" not in ext:
        return True
    module_name, class_name = ext.split(":", 1)
    try:
        cls = getattr(importlib.import_module(module_name), class_name)
    except (ImportError, AttributeError, ValueError):
        return False
    return isinstance(cls, type) and issubclass(cls, markdown.Extension)


class MarkdownRenderer:
    """Converts Markdown content to HTML using MkDocs-compatible extensions."""

    def __init__(
        self,
        extensions: list[str | dict[str, Any]],
        docs_dir: Path,
        mermaid_output_dir: Path | None = None,
        project_root: Path | None = None,
        mermaid_server: str | None = None,
        mermaid_public_only: bool = False,
        asset_roots: Iterable[Path] = (),
    ) -> None:
        self._docs_dir = docs_dir
        self._mermaid_server = mermaid_server
        self._mermaid_public_only = mermaid_public_only
        # Directories that content may reference files from: the mkdocs.yml
        # directory, docs_dir, and any extra roots such as the conversion
        # source (so a monorepo page can use ../../shared/logo.png).
        self._project_root = (project_root or docs_dir.parent).resolve()
        self._asset_policy = AssetPolicy([self._project_root, docs_dir, *asset_roots])
        self.config_warnings: list[str] = []
        self._mermaid_output_dir = mermaid_output_dir
        self._extension_names: list[str] = []
        self._extension_configs: dict[str, dict[str, Any]] = {}
        self.extension_load_results: list[tuple[str, bool, str]] = []
        self.unresolved_assets: list[tuple[str, str]] = []
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
            if not _is_extension_class_ref(ext):
                self.extension_load_results.append(
                    (ext, False, "not a Markdown Extension class; refusing to load")
                )
                continue
            try:
                markdown.Markdown(extensions=[ext])
                valid_extensions.append(ext)
                self.extension_load_results.append((ext, True, ""))
            except Exception as exc:
                self.extension_load_results.append((ext, False, str(exc)))

        # Ensure superfences routes mermaid blocks through our callable formatter.
        # MkDocs configs often use !!python/name: YAML tags for the format function
        # which safe_load cannot resolve, leaving a raw string instead of a callable.
        # We always replace/inject our own mermaid fence with a real function.
        configs = dict(self._extension_configs)
        sf_cfg = configs.setdefault("pymdownx.superfences", {})
        fences = sf_cfg.get("custom_fences", [])
        fences = [f for f in fences if f.get("name") != "mermaid"]
        fences.append({"name": "mermaid", "class": "mermaid", "format": _mermaid_fence_format})
        sf_cfg["custom_fences"] = fences
        configs["pymdownx.superfences"] = sf_cfg

        for ext in valid_extensions:
            module_name = ext.split(":", 1)[0]
            if module_name == "pymdownx.snippets":
                configs[ext] = self._sanitize_snippets_config(configs.get(ext, {}))
            elif module_name == "pymdownx.b64":
                configs[ext] = self._sanitize_b64_config(configs.get(ext, {}))

        return markdown.Markdown(
            extensions=valid_extensions,
            extension_configs=configs,
            output_format="html",
        )

    def _confine_base_paths(self, raw: Any, ext_name: str) -> list[str]:
        """Resolve base paths against the project root, dropping any outside it."""
        entries = raw if isinstance(raw, list) else [raw] if raw else []
        confined: list[str] = []
        for entry in entries:
            if not isinstance(entry, str):
                continue
            candidate = (self._project_root / entry).resolve()
            if candidate.is_relative_to(self._project_root):
                confined.append(str(candidate))
            else:
                self.config_warnings.append(
                    f"{ext_name}: ignoring base_path outside the project: {entry}"
                )
        return confined or [str(self._project_root)]

    def _sanitize_snippets_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """Keep pymdownx.snippets from including files outside the project or URLs.

        Relative base paths are resolved against the project root (as MkDocs
        does) rather than the current working directory.
        """
        config = dict(config)
        config["base_path"] = self._confine_base_paths(
            config.get("base_path", ["."]), "pymdownx.snippets"
        )
        if config.get("restrict_base_path") is False:
            self.config_warnings.append(
                "pymdownx.snippets: restrict_base_path: false is not supported; forcing true"
            )
        config["restrict_base_path"] = True
        if config.get("url_download"):
            self.config_warnings.append(
                "pymdownx.snippets: url_download is disabled for security; "
                "remote snippets will not be included"
            )
        config["url_download"] = False
        return config

    def _sanitize_b64_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """Keep pymdownx.b64 from inlining images from outside the project."""
        config = dict(config)
        base = self._confine_base_paths(config.get("base_path", "."), "pymdownx.b64")[0]
        config["base_path"] = base
        config["root_path"] = str(self._project_root)
        config["restrict_path"] = True
        return config

    def render(self, md_content: str, source_path: Path) -> tuple[str, list[str]]:
        """Convert a single Markdown string to HTML.

        Args:
            md_content: Raw Markdown text.
            source_path: Path to the .md file (for resolving relative links/images).

        Returns:
            Tuple of (HTML string, list of warning messages).
        """
        self._md.reset()
        self.unresolved_assets = []
        html = self._md.convert(md_content)
        html = self._resolve_relative_assets(html, source_path)
        html = self._resolve_emoji_shortcodes(html)
        html = self._render_annotations(html)
        html, warnings = self._render_mermaid_blocks(html, source_path)
        return html, warnings

    def _resolve_relative_assets(self, html: str, source_path: Path) -> str:
        """Rewrite relative image src and link href to absolute file:// paths."""
        source_dir = source_path.parent

        def _rewrite_src(match: re.Match[str]) -> str:
            attr = match.group(1)  # src or href
            quote = match.group(2)
            path = match.group(3)

            # Absolute file:// URIs (from raw HTML) must stay inside the project.
            # Links are left alone; only embedded resources (src) are read.
            if path.startswith("file:"):
                if attr == "href" or self._asset_policy.allows_uri(path):
                    return match.group(0)
                return self._blocked(source_path, path)

            # Skip absolute URLs and anchors
            if path.startswith(("http://", "https://", "#", "mailto:", "data:")):
                return match.group(0)

            resolved = (source_dir / path).resolve()
            if not self._asset_policy.allows(resolved):
                if attr == "href":
                    return match.group(0)
                return self._blocked(source_path, path)
            if resolved.exists():
                return f"{attr}={quote}{resolved.as_uri()}{quote}"
            # Track images that could not be resolved
            if attr == "src":
                self.unresolved_assets.append((str(source_path), path))
            return match.group(0)

        # Match src="..." and href="..." (but not external URLs)
        html = re.sub(
            r'(src|href)=(["\'])((?!https?://|#|mailto:)[^"\']+)\2',
            _rewrite_src,
            html,
        )
        return html

    def _blocked(self, source_path: Path, path: str) -> str:
        """Blank out an embedded resource outside the project and record it."""
        self.unresolved_assets.append((str(source_path), f"{path} (blocked: outside project)"))
        return 'src=""'

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

    def _render_mermaid_blocks(self, html: str, source_path: Path) -> tuple[str, list[str]]:
        """Render mermaid code blocks to PNG images."""
        if self._mermaid_output_dir is None:
            return html, []

        from leafpress.mermaid import render_mermaid_blocks

        return render_mermaid_blocks(
            html,
            self._mermaid_output_dir,
            source_path,
            server=self._mermaid_server,
            require_public_host=self._mermaid_public_only,
        )
