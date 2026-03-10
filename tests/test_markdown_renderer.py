"""Tests for markdown_renderer module."""

from pathlib import Path

from leafpress.markdown_renderer import MarkdownRenderer


def test_basic_rendering(sample_mkdocs_dir: Path) -> None:
    renderer = MarkdownRenderer(
        extensions=["tables", "toc"],
        docs_dir=sample_mkdocs_dir / "docs",
    )
    html = renderer.render("# Hello\n\nWorld", sample_mkdocs_dir / "docs" / "index.md")
    assert "<h1" in html
    assert "Hello" in html
    assert "World" in html


def test_table_rendering(sample_mkdocs_dir: Path) -> None:
    renderer = MarkdownRenderer(
        extensions=["tables"],
        docs_dir=sample_mkdocs_dir / "docs",
    )
    md = "| A | B |\n|---|---|\n| 1 | 2 |"
    html = renderer.render(md, sample_mkdocs_dir / "docs" / "index.md")
    assert "<table" in html
    assert "<th" in html or "<td" in html


def test_code_block_rendering(sample_mkdocs_dir: Path) -> None:
    renderer = MarkdownRenderer(
        extensions=[],
        docs_dir=sample_mkdocs_dir / "docs",
    )
    md = "```python\nprint('hi')\n```"
    html = renderer.render(md, sample_mkdocs_dir / "docs" / "index.md")
    assert "<code" in html or "<pre" in html


def test_unavailable_extension_skipped(sample_mkdocs_dir: Path) -> None:
    """Unknown extensions should be skipped, not crash."""
    renderer = MarkdownRenderer(
        extensions=["nonexistent_extension_xyz"],
        docs_dir=sample_mkdocs_dir / "docs",
    )
    html = renderer.render("# Test", sample_mkdocs_dir / "docs" / "index.md")
    assert "Test" in html
