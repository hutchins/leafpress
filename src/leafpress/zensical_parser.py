"""Read a Zensical ``zensical.toml`` into the same shape as a parsed mkdocs.yml.

Experimental: Zensical (the successor to Material for MkDocs) is pre-1.0 and
its configuration format may still change. Only the settings leafpress uses
are read: ``site_name``, ``docs_dir``, ``nav``, ``markdown_extensions``,
``theme``, and ``extra_css``, all from the ``[project]`` table.

Two differences from mkdocs.yml are handled here:

- ``markdown_extensions`` is a TOML table, and dotted names nest:
  ``[project.markdown_extensions.pymdownx.superfences]`` parses as
  ``{"pymdownx": {"superfences": {...}}}``. :func:`flatten_markdown_extensions`
  turns that back into mkdocs-style ``["name", {"name": {config}}]`` entries.
- Python callables are written as plain dotted-name strings (mkdocs.yml uses
  ``!!python/name:`` tags), so those settings are dropped like the tags are.

Parsing uses ``tomli`` rather than the stdlib ``tomllib`` because real
zensical.toml files use TOML 1.1 syntax (e.g. newlines inside inline tables),
which Zensical accepts but ``tomllib`` rejects.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import tomli

from leafpress.exceptions import ConfigError

# Package prefixes whose TOML sub-tables are individual extensions
_EXTENSION_NAMESPACES = {
    "pymdownx",
    "markdown",
    "markdown.extensions",
    "material",
    "material.extensions",
    "zensical",
    "zensical.extensions",
}

# Extension settings that name a Python callable; as strings they can't be used
_CALLABLE_SETTINGS = {
    "emoji_index",
    "emoji_generator",
    "slugify",
    "format",
    "validator",
    "title_formatter",
}


def load_zensical_project(config_path: Path) -> dict[str, Any]:
    """Load ``[project]`` from a zensical.toml as a mkdocs.yml-style dict.

    Raises:
        ConfigError: If the file isn't valid TOML or has no ``[project]`` table.
    """
    try:
        data = tomli.loads(config_path.read_text(encoding="utf-8"))
    except (tomli.TOMLDecodeError, UnicodeDecodeError) as e:
        raise ConfigError(f"Invalid TOML in {config_path}: {e}") from e

    project = data.get("project")
    if not isinstance(project, dict):
        raise ConfigError(f"No [project] table in {config_path}")

    raw = dict(project)
    extensions = project.get("markdown_extensions", {})
    raw["markdown_extensions"] = (
        flatten_markdown_extensions(extensions) if isinstance(extensions, dict) else []
    )
    return raw


def flatten_markdown_extensions(table: dict[str, Any]) -> list[str | dict[str, Any]]:
    """Convert a TOML ``markdown_extensions`` table into mkdocs.yml list form.

    Example:
        >>> flatten_markdown_extensions({"admonition": {}, "pymdownx": {"details": {}}})
        ['admonition', 'pymdownx.details']
    """
    entries: list[str | dict[str, Any]] = []
    _walk(table, "", entries)
    return entries


def _walk(node: dict[str, Any], prefix: str, entries: list[str | dict[str, Any]]) -> None:
    for key, value in node.items():
        name = f"{prefix}.{key}" if prefix else key
        if value is False:
            continue  # explicitly disabled
        if isinstance(value, dict) and _is_namespace(name, value):
            _walk(value, name, entries)
            continue
        config = _clean_config(value) if isinstance(value, dict) else {}
        entries.append({name: config} if config else name)


def _is_namespace(name: str, value: dict[str, Any]) -> bool:
    """Whether ``name`` is a package prefix rather than an extension."""
    if name in _EXTENSION_NAMESPACES:
        return True
    if not value or not all(isinstance(v, dict) for v in value.values()):
        return False
    # e.g. [project.markdown_extensions.mypkg.ext]: mypkg.ext is a module
    first_child = next(iter(value))
    try:
        return importlib.util.find_spec(f"{name}.{first_child}") is not None
    except (ImportError, ValueError):
        return False


def _clean_config(config: dict[str, Any]) -> dict[str, Any]:
    """Drop callable-by-name settings, including custom fences' ``format``."""
    cleaned: dict[str, Any] = {}
    for key, value in config.items():
        if key in _CALLABLE_SETTINGS and isinstance(value, str):
            continue
        if key == "custom_fences" and isinstance(value, list):
            value = [
                {k: v for k, v in fence.items() if not (k == "format" and isinstance(v, str))}
                for fence in value
                if isinstance(fence, dict)
            ]
        cleaned[key] = value
    return cleaned
