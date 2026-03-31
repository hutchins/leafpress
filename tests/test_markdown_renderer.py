"""Tests for markdown_renderer module."""

from pathlib import Path
from unittest.mock import patch

from leafpress.markdown_renderer import MarkdownRenderer


def test_basic_rendering(sample_mkdocs_dir: Path) -> None:
    renderer = MarkdownRenderer(
        extensions=["tables", "toc"],
        docs_dir=sample_mkdocs_dir / "docs",
    )
    html, _ = renderer.render("# Hello\n\nWorld", sample_mkdocs_dir / "docs" / "index.md")
    assert "<h1" in html
    assert "Hello" in html
    assert "World" in html


def test_table_rendering(sample_mkdocs_dir: Path) -> None:
    renderer = MarkdownRenderer(
        extensions=["tables"],
        docs_dir=sample_mkdocs_dir / "docs",
    )
    md = "| A | B |\n|---|---|\n| 1 | 2 |"
    html, _ = renderer.render(md, sample_mkdocs_dir / "docs" / "index.md")
    assert "<table" in html
    assert "<th" in html or "<td" in html


def test_code_block_rendering(sample_mkdocs_dir: Path) -> None:
    renderer = MarkdownRenderer(
        extensions=[],
        docs_dir=sample_mkdocs_dir / "docs",
    )
    md = "```python\nprint('hi')\n```"
    html, _ = renderer.render(md, sample_mkdocs_dir / "docs" / "index.md")
    assert "<code" in html or "<pre" in html


def test_unavailable_extension_skipped(sample_mkdocs_dir: Path) -> None:
    """Unknown extensions should be skipped, not crash."""
    renderer = MarkdownRenderer(
        extensions=["nonexistent_extension_xyz"],
        docs_dir=sample_mkdocs_dir / "docs",
    )
    html, _ = renderer.render("# Test", sample_mkdocs_dir / "docs" / "index.md")
    assert "Test" in html


def test_extension_load_failure_includes_error_message(sample_mkdocs_dir: Path) -> None:
    """Failed extensions should record the error message."""
    renderer = MarkdownRenderer(
        extensions=["nonexistent_extension_xyz"],
        docs_dir=sample_mkdocs_dir / "docs",
    )
    failed = [(ext, ok, msg) for ext, ok, msg in renderer.extension_load_results if not ok]
    assert len(failed) >= 1
    ext, ok, msg = failed[0]
    assert ext == "nonexistent_extension_xyz"
    assert msg != ""


def test_extension_load_success_has_empty_error(sample_mkdocs_dir: Path) -> None:
    """Successfully loaded extensions should have an empty error string."""
    renderer = MarkdownRenderer(
        extensions=["tables"],
        docs_dir=sample_mkdocs_dir / "docs",
    )
    tables_results = [
        (ext, ok, msg) for ext, ok, msg in renderer.extension_load_results if ext == "tables"
    ]
    assert len(tables_results) == 1
    _, ok, msg = tables_results[0]
    assert ok is True
    assert msg == ""


def test_unresolved_assets_tracked(tmp_path: Path) -> None:
    """Missing image references should be tracked in unresolved_assets."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    md_file = docs_dir / "page.md"
    md_file.write_text("![alt](nonexistent.png)")

    renderer = MarkdownRenderer(extensions=[], docs_dir=docs_dir)
    renderer.render("![alt](nonexistent.png)", md_file)

    assert len(renderer.unresolved_assets) == 1
    assert renderer.unresolved_assets[0][1] == "nonexistent.png"


def test_resolved_assets_not_tracked(tmp_path: Path) -> None:
    """Existing image references should not appear in unresolved_assets."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    img = docs_dir / "exists.png"
    img.write_bytes(b"\x89PNG")
    md_file = docs_dir / "page.md"
    md_file.write_text("![alt](exists.png)")

    renderer = MarkdownRenderer(extensions=[], docs_dir=docs_dir)
    renderer.render("![alt](exists.png)", md_file)

    assert renderer.unresolved_assets == []


def test_external_urls_not_tracked(tmp_path: Path) -> None:
    """External URLs should not be tracked as unresolved."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    md_file = docs_dir / "page.md"

    renderer = MarkdownRenderer(extensions=[], docs_dir=docs_dir)
    renderer.render("![alt](https://example.com/img.png)", md_file)

    assert renderer.unresolved_assets == []


def test_unresolved_assets_reset_between_renders(tmp_path: Path) -> None:
    """Each render() call should start with a fresh unresolved_assets list."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    md_file = docs_dir / "page.md"

    renderer = MarkdownRenderer(extensions=[], docs_dir=docs_dir)
    renderer.render("![alt](missing1.png)", md_file)
    assert len(renderer.unresolved_assets) == 1

    renderer.render("![alt](missing2.png)", md_file)
    assert len(renderer.unresolved_assets) == 1
    assert renderer.unresolved_assets[0][1] == "missing2.png"


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
    mock_return = (mock_html, [])
    with patch("leafpress.mermaid.render_mermaid_blocks", return_value=mock_return) as mock_render:
        html, _ = renderer.render(
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
    html, _ = renderer.render(md, sample_mkdocs_dir / "docs" / "index.md")
    assert "graph TD" in html
