"""Parse mkdocs.yml to extract nav structure, extensions, and docs directory."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from leafpress.exceptions import ConfigError


class _MkDocsLoader(yaml.SafeLoader):
    """Custom YAML loader that handles !!python/name: and !!python/object: tags.

    MkDocs configs (especially Material for MkDocs) use these tags for
    extension callbacks. We resolve them to placeholder strings so the
    rest of the config can be parsed safely.
    """


def _python_name_constructor(loader: yaml.Loader, node: yaml.Node) -> str:
    """Convert !!python/name:some.module.func to a string placeholder."""
    return f"!!python/name:{node.value}"


def _python_object_constructor(loader: yaml.Loader, node: yaml.Node) -> str:
    """Convert !!python/object: tags to a string placeholder."""
    return f"!!python/object:{node.value}"


_MkDocsLoader.add_constructor("tag:yaml.org,2002:python/name:", _python_name_constructor)
_MkDocsLoader.add_multi_constructor(
    "tag:yaml.org,2002:python/name:", lambda loader, suffix, node: f"!!python/name:{node.value}"
)
_MkDocsLoader.add_multi_constructor(
    "tag:yaml.org,2002:python/object:", lambda loader, suffix, node: f"!!python/object:{node.value}"
)


@dataclass
class NavItem:
    """A single navigation entry -- either a page or a section with children."""

    title: str
    path: Path | None = None
    children: list[NavItem] = field(default_factory=list)
    level: int = 0


@dataclass
class MkDocsConfig:
    """Parsed representation of an mkdocs.yml relevant to leafpress."""

    site_name: str
    docs_dir: Path
    nav_items: list[NavItem]
    markdown_extensions: list[str | dict[str, Any]]
    theme_name: str | None
    extra_css: list[str]
    config_path: Path


def parse_mkdocs_config(config_path: Path) -> MkDocsConfig:
    """Parse mkdocs.yml and return structured config."""
    if not config_path.exists():
        raise ConfigError(f"MkDocs config not found: {config_path}")

    try:
        with open(config_path) as f:
            raw = yaml.load(f, Loader=_MkDocsLoader)  # noqa: S506
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in {config_path}: {e}") from e

    if raw is None:
        raise ConfigError(f"Empty mkdocs config: {config_path}")

    site_name = raw.get("site_name", "Untitled")
    docs_dir_str = raw.get("docs_dir", "docs")
    docs_dir = (config_path.parent / docs_dir_str).resolve()

    if not docs_dir.is_dir():
        raise ConfigError(f"docs_dir not found: {docs_dir}")

    # Parse navigation
    nav_raw = raw.get("nav")
    if nav_raw:
        nav_items = _parse_nav(nav_raw, docs_dir, level=0)
    else:
        nav_items = _auto_discover_nav(docs_dir)

    # Parse extensions
    extensions = raw.get("markdown_extensions", [])

    # Theme
    theme_raw = raw.get("theme")
    theme_name = None
    if isinstance(theme_raw, str):
        theme_name = theme_raw
    elif isinstance(theme_raw, dict):
        theme_name = theme_raw.get("name")

    extra_css = raw.get("extra_css", [])

    return MkDocsConfig(
        site_name=site_name,
        docs_dir=docs_dir,
        nav_items=nav_items,
        markdown_extensions=extensions,
        theme_name=theme_name,
        extra_css=extra_css,
        config_path=config_path.resolve(),
    )


def _parse_nav(nav_raw: list[Any], docs_dir: Path, level: int = 0) -> list[NavItem]:
    """Recursively parse the nav YAML structure.

    Handles three forms:
      - "path.md"                     -> page with auto-title
      - {"Title": "path.md"}         -> page with explicit title
      - {"Section Title": [children]} -> section with nested pages
    """
    items: list[NavItem] = []

    for entry in nav_raw:
        if isinstance(entry, str):
            # Bare path
            title = _title_from_path(entry)
            items.append(NavItem(title=title, path=Path(entry), level=level))
        elif isinstance(entry, dict):
            for title, value in entry.items():
                if isinstance(value, str):
                    # Explicit title with path
                    items.append(NavItem(title=title, path=Path(value), level=level))
                elif isinstance(value, list):
                    # Section with children
                    children = _parse_nav(value, docs_dir, level=level + 1)
                    items.append(NavItem(title=title, path=None, children=children, level=level))

    return items


def _auto_discover_nav(docs_dir: Path) -> list[NavItem]:
    """Auto-discover markdown files when no nav is defined."""
    items: list[NavItem] = []
    md_files = sorted(docs_dir.rglob("*.md"))

    for md_file in md_files:
        rel_path = md_file.relative_to(docs_dir)
        title = _title_from_path(str(rel_path))
        items.append(NavItem(title=title, path=rel_path, level=0))

    return items


def _title_from_path(path_str: str) -> str:
    """Derive a human-readable title from a file path."""
    name = Path(path_str).stem
    if name == "index":
        parent = Path(path_str).parent
        if parent == Path("."):
            return "Home"
        name = parent.name
    return name.replace("-", " ").replace("_", " ").title()


def flatten_nav(items: list[NavItem]) -> list[NavItem]:
    """Flatten nested nav into an ordered list of pages (depth-first).

    Section nodes (path=None) are kept as heading markers.
    """
    result: list[NavItem] = []
    for item in items:
        result.append(item)
        if item.children:
            result.extend(flatten_nav(item.children))
    return result
