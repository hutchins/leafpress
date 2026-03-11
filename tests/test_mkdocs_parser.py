"""Tests for mkdocs_parser module."""

from pathlib import Path

import pytest

from leafpress.exceptions import ConfigError
from leafpress.mkdocs_parser import (
    NavItem,
    bump_nav_levels,
    flatten_nav,
    parse_mkdocs_config,
)


def test_parse_sample_project(sample_mkdocs_config: Path) -> None:
    config = parse_mkdocs_config(sample_mkdocs_config)
    assert config.site_name == "Test Documentation"
    assert config.docs_dir.exists()
    assert len(config.nav_items) == 2
    assert config.nav_items[0].title == "Home"
    assert config.nav_items[0].path == Path("index.md")


def test_parse_nav_section(sample_mkdocs_config: Path) -> None:
    config = parse_mkdocs_config(sample_mkdocs_config)
    section = config.nav_items[1]
    assert section.title == "Getting Started"
    assert section.path is None
    assert len(section.children) == 1
    assert section.children[0].title == "Installation"


def test_flatten_nav() -> None:
    items = [
        NavItem(title="Home", path=Path("index.md"), level=0),
        NavItem(
            title="Section",
            path=None,
            level=0,
            children=[
                NavItem(title="Page A", path=Path("a.md"), level=1),
                NavItem(title="Page B", path=Path("b.md"), level=1),
            ],
        ),
    ]
    flat = flatten_nav(items)
    assert len(flat) == 4
    assert flat[0].title == "Home"
    assert flat[1].title == "Section"
    assert flat[2].title == "Page A"
    assert flat[3].title == "Page B"


def test_bump_nav_levels() -> None:
    items = [
        NavItem(title="Home", path=Path("index.md"), level=0),
        NavItem(title="Section", path=None, level=0),
        NavItem(title="Page A", path=Path("a.md"), level=1),
    ]
    bumped = bump_nav_levels(items)
    assert bumped[0].level == 1
    assert bumped[1].level == 1
    assert bumped[2].level == 2
    # Original items are unchanged
    assert items[0].level == 0


def test_bump_nav_levels_custom_increment() -> None:
    items = [NavItem(title="Page", path=Path("p.md"), level=0)]
    bumped = bump_nav_levels(items, increment=3)
    assert bumped[0].level == 3


def test_parse_missing_config(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        parse_mkdocs_config(tmp_path / "nonexistent.yml")


def test_parse_extensions(sample_mkdocs_config: Path) -> None:
    config = parse_mkdocs_config(sample_mkdocs_config)
    ext_names = [
        e if isinstance(e, str) else next(iter(e.keys()))
        for e in config.markdown_extensions
    ]
    assert "admonition" in ext_names
    assert "tables" in ext_names
