"""Tests for markdown_renderer module."""

from pathlib import Path
from unittest.mock import patch

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


def test_mermaid_blocks_rendered_when_output_dir_set(
    sample_mkdocs_dir: Path, tmp_path: Path
) -> None:
    """Mermaid code blocks should be replaced with images when output dir is set."""
    renderer = MarkdownRenderer(
        extensions=[],
        docs_dir=sample_mkdocs_dir / "docs",
        mermaid_output_dir=tmp_path,
    )
    mock_html = "<img"
    with patch("leafpress.mermaid.render_mermaid_blocks", return_value=mock_html) as mock_render:
        html = renderer.render(
            "```mermaid\ngraph TD\n    A --> B\n```",
            sample_mkdocs_dir / "docs" / "index.md",
        )
        mock_render.assert_called_once()

    assert "<img" in html


def test_mermaid_blocks_skipped_when_no_output_dir(sample_mkdocs_dir: Path) -> None:
    """Without mermaid_output_dir, mermaid blocks should pass through unchanged."""
    renderer = MarkdownRenderer(
        extensions=[],
        docs_dir=sample_mkdocs_dir / "docs",
    )
    md = "```mermaid\ngraph TD\n    A --> B\n```"
    html = renderer.render(md, sample_mkdocs_dir / "docs" / "index.md")
    assert "graph TD" in html
