"""Tests for consolidated Markdown export renderer."""

from pathlib import Path

from typer.testing import CliRunner

from leafpress.cli import cli
from leafpress.markdown_export.renderer import MarkdownExportRenderer
from leafpress.mkdocs_parser import MkDocsConfig, NavItem

runner = CliRunner()


def _make_mkdocs_cfg(docs_dir: Path) -> MkDocsConfig:
    """Create a minimal MkDocsConfig pointing at a docs directory."""
    return MkDocsConfig(
        site_name="Test Site",
        docs_dir=docs_dir,
        nav_items=[],
        markdown_extensions=[],
        theme_name="material",
        extra_css=[],
        config_path=docs_dir.parent / "mkdocs.yml",
    )


def _make_pages(docs_dir: Path) -> list[tuple[NavItem, str]]:
    """Create sample pages with matching .md files on disk."""
    (docs_dir / "index.md").write_text("# Welcome\n\nThis is the home page.\n")
    (docs_dir / "guide.md").write_text("# User Guide\n\nStep-by-step instructions.\n")

    return [
        (NavItem(title="Home", path=Path("index.md"), level=0), "<h1>Welcome</h1>"),
        (NavItem(title="Guide", path=Path("guide.md"), level=0), "<h1>User Guide</h1>"),
    ]


def test_markdown_export_basic(tmp_path: Path) -> None:
    """Produces a .md file with content from all pages."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    pages = _make_pages(docs_dir)
    cfg = _make_mkdocs_cfg(docs_dir)
    out = tmp_path / "output.md"

    renderer = MarkdownExportRenderer(None, None, cfg)
    renderer.render(pages, out, cover_page=False, include_toc=False)

    content = out.read_text()
    assert "Welcome" in content
    assert "User Guide" in content
    assert content.endswith("\n")


def test_markdown_export_toc(tmp_path: Path) -> None:
    """TOC section present when include_toc=True."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    pages = _make_pages(docs_dir)
    cfg = _make_mkdocs_cfg(docs_dir)
    out = tmp_path / "output.md"

    renderer = MarkdownExportRenderer(None, None, cfg)
    renderer.render(pages, out, cover_page=False, include_toc=True)

    content = out.read_text()
    assert "## Table of Contents" in content
    assert "[Home]" in content
    assert "[Guide]" in content


def test_markdown_export_no_toc(tmp_path: Path) -> None:
    """No TOC when include_toc=False."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    pages = _make_pages(docs_dir)
    cfg = _make_mkdocs_cfg(docs_dir)
    out = tmp_path / "output.md"

    renderer = MarkdownExportRenderer(None, None, cfg)
    renderer.render(pages, out, cover_page=False, include_toc=False)

    content = out.read_text()
    assert "Table of Contents" not in content


def test_markdown_export_cover_metadata(tmp_path: Path) -> None:
    """Front matter present with title/author/date when cover_page=True."""
    from leafpress.config import BrandingConfig

    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    pages = _make_pages(docs_dir)
    cfg = _make_mkdocs_cfg(docs_dir)
    branding = BrandingConfig(
        company_name="Acme Corp",
        project_name="Test Project",
        author="Jane Doe",
    )
    out = tmp_path / "output.md"

    renderer = MarkdownExportRenderer(branding, None, cfg)
    renderer.render(pages, out, cover_page=True, include_toc=False)

    content = out.read_text()
    assert content.startswith("---\n")
    assert 'title: "Test Project"' in content
    assert 'company: "Acme Corp"' in content
    assert 'author: "Jane Doe"' in content
    assert "date:" in content


def test_markdown_export_no_cover(tmp_path: Path) -> None:
    """No front matter when cover_page=False."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    pages = _make_pages(docs_dir)
    cfg = _make_mkdocs_cfg(docs_dir)
    out = tmp_path / "output.md"

    renderer = MarkdownExportRenderer(None, None, cfg)
    renderer.render(pages, out, cover_page=False, include_toc=False)

    content = out.read_text()
    assert not content.startswith("---\n")


def test_markdown_export_page_separators(tmp_path: Path) -> None:
    """Pages separated by horizontal rules."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    pages = _make_pages(docs_dir)
    cfg = _make_mkdocs_cfg(docs_dir)
    out = tmp_path / "output.md"

    renderer = MarkdownExportRenderer(None, None, cfg)
    renderer.render(pages, out, cover_page=False, include_toc=False)

    content = out.read_text()
    assert "\n\n---\n\n" in content


def test_markdown_export_missing_page_skipped(tmp_path: Path) -> None:
    """Missing .md file is skipped without crashing."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "index.md").write_text("# Welcome\n")

    pages = [
        (NavItem(title="Home", path=Path("index.md"), level=0), "<h1>Welcome</h1>"),
        (NavItem(title="Missing", path=Path("gone.md"), level=0), "<h1>Gone</h1>"),
    ]
    cfg = _make_mkdocs_cfg(docs_dir)
    out = tmp_path / "output.md"

    renderer = MarkdownExportRenderer(None, None, cfg)
    renderer.render(pages, out, cover_page=False, include_toc=False)

    content = out.read_text()
    assert "Welcome" in content
    assert "Gone" not in content


def test_markdown_export_section_dividers(tmp_path: Path) -> None:
    """Section dividers (path=None) render as headings."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "page.md").write_text("# Content\n")

    pages = [
        (NavItem(title="Part One", path=None, level=0), ""),
        (NavItem(title="Page", path=Path("page.md"), level=1), "<h1>Content</h1>"),
    ]
    cfg = _make_mkdocs_cfg(docs_dir)
    out = tmp_path / "output.md"

    renderer = MarkdownExportRenderer(None, None, cfg)
    renderer.render(pages, out, cover_page=False, include_toc=False)

    content = out.read_text()
    assert "# Part One" in content


def test_markdown_export_cli(sample_mkdocs_dir: Path, tmp_output: Path) -> None:
    """End-to-end CLI test: leafpress convert -f markdown."""
    result = runner.invoke(
        cli,
        ["convert", str(sample_mkdocs_dir), "-f", "markdown", "-o", str(tmp_output)],
    )
    assert result.exit_code == 0
    md_files = list(tmp_output.glob("*.md"))
    assert len(md_files) == 1
    content = md_files[0].read_text()
    assert len(content) > 0
