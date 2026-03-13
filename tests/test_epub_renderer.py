"""Tests for EPUB renderer."""

import zipfile
from pathlib import Path

import pytest

from leafpress.config import WatermarkConfig, load_config
from leafpress.epub.renderer import EpubRenderer
from leafpress.git_info import extract_git_info
from leafpress.markdown_renderer import MarkdownRenderer
from leafpress.mkdocs_parser import flatten_nav, parse_mkdocs_config


@pytest.fixture
def html_pages(sample_mkdocs_config: Path):
    """Render all pages from sample MkDocs project."""
    mkdocs_cfg = parse_mkdocs_config(sample_mkdocs_config)
    renderer = MarkdownRenderer(
        extensions=mkdocs_cfg.markdown_extensions,
        docs_dir=mkdocs_cfg.docs_dir,
    )
    pages = flatten_nav(mkdocs_cfg.nav_items)
    result = []
    for item in pages:
        if item.path is None:
            result.append((item, ""))
            continue
        md_file = mkdocs_cfg.docs_dir / item.path
        html, _ = renderer.render(md_file.read_text(), md_file)
        result.append((item, html))
    return result, mkdocs_cfg


def test_epub_generation(
    sample_mkdocs_config: Path,
    sample_branding_config: Path,
    tmp_output: Path,
) -> None:
    mkdocs_cfg = parse_mkdocs_config(sample_mkdocs_config)
    branding = load_config(sample_branding_config)
    git_info = extract_git_info(sample_mkdocs_config.parent)

    renderer = MarkdownRenderer(
        extensions=mkdocs_cfg.markdown_extensions,
        docs_dir=mkdocs_cfg.docs_dir,
    )

    pages = flatten_nav(mkdocs_cfg.nav_items)
    html_pages = []
    for item in pages:
        if item.path is None:
            html_pages.append((item, ""))
            continue
        md_file = mkdocs_cfg.docs_dir / item.path
        html, _ = renderer.render(md_file.read_text(), md_file)
        html_pages.append((item, html))

    epub_path = tmp_output / "test.epub"
    epub_renderer = EpubRenderer(branding, git_info, mkdocs_cfg)
    epub_renderer.render(html_pages, epub_path)

    assert epub_path.exists()
    assert epub_path.stat().st_size > 0
    # EPUB is a valid ZIP file
    assert zipfile.is_zipfile(epub_path)


def test_epub_without_branding(
    sample_mkdocs_config: Path,
    tmp_output: Path,
) -> None:
    mkdocs_cfg = parse_mkdocs_config(sample_mkdocs_config)
    renderer = MarkdownRenderer(
        extensions=mkdocs_cfg.markdown_extensions,
        docs_dir=mkdocs_cfg.docs_dir,
    )

    pages = flatten_nav(mkdocs_cfg.nav_items)
    html_pages = []
    for item in pages:
        if item.path is None:
            html_pages.append((item, ""))
            continue
        md_file = mkdocs_cfg.docs_dir / item.path
        html, _ = renderer.render(md_file.read_text(), md_file)
        html_pages.append((item, html))

    epub_path = tmp_output / "no_branding.epub"
    epub_renderer = EpubRenderer(None, None, mkdocs_cfg)
    epub_renderer.render(html_pages, epub_path, cover_page=False, include_toc=False)

    assert epub_path.exists()
    assert epub_path.stat().st_size > 0


def test_epub_metadata(
    html_pages,
    sample_branding_config: Path,
    tmp_output: Path,
) -> None:
    pages, mkdocs_cfg = html_pages
    branding = load_config(sample_branding_config)

    epub_path = tmp_output / "metadata.epub"
    epub_renderer = EpubRenderer(branding, None, mkdocs_cfg)
    epub_renderer.render(pages, epub_path)

    with zipfile.ZipFile(epub_path) as zf:
        # Check that content.opf exists and contains metadata
        opf_names = [n for n in zf.namelist() if n.endswith(".opf")]
        assert opf_names
        opf_content = zf.read(opf_names[0]).decode()
        assert branding.project_name in opf_content


def test_epub_contains_chapters(
    html_pages,
    sample_branding_config: Path,
    tmp_output: Path,
) -> None:
    pages, mkdocs_cfg = html_pages
    branding = load_config(sample_branding_config)

    epub_path = tmp_output / "chapters.epub"
    epub_renderer = EpubRenderer(branding, None, mkdocs_cfg)
    epub_renderer.render(pages, epub_path)

    with zipfile.ZipFile(epub_path) as zf:
        xhtml_files = [n for n in zf.namelist() if n.endswith(".xhtml")]
        # Should have cover + chapters + footer
        assert len(xhtml_files) >= 2


def test_epub_contains_css(
    html_pages,
    sample_branding_config: Path,
    tmp_output: Path,
) -> None:
    pages, mkdocs_cfg = html_pages
    branding = load_config(sample_branding_config)

    epub_path = tmp_output / "css.epub"
    epub_renderer = EpubRenderer(branding, None, mkdocs_cfg)
    epub_renderer.render(pages, epub_path)

    with zipfile.ZipFile(epub_path) as zf:
        css_files = [n for n in zf.namelist() if n.endswith(".css")]
        assert css_files
        css_content = zf.read(css_files[0]).decode()
        assert "LeafPress" in css_content


def test_epub_no_cover_page(
    html_pages,
    sample_branding_config: Path,
    tmp_output: Path,
) -> None:
    pages, mkdocs_cfg = html_pages
    branding = load_config(sample_branding_config)

    epub_path = tmp_output / "no_cover.epub"
    epub_renderer = EpubRenderer(branding, None, mkdocs_cfg)
    epub_renderer.render(pages, epub_path, cover_page=False)

    with zipfile.ZipFile(epub_path) as zf:
        names = zf.namelist()
        cover_files = [n for n in names if "cover" in n.lower() and n.endswith(".xhtml")]
        assert not cover_files


def test_epub_with_watermark(
    html_pages,
    sample_branding_config: Path,
    tmp_output: Path,
) -> None:
    pages, mkdocs_cfg = html_pages
    branding = load_config(sample_branding_config)
    branding.watermark = WatermarkConfig(text="DRAFT")

    epub_path = tmp_output / "watermark.epub"
    epub_renderer = EpubRenderer(branding, None, mkdocs_cfg)
    epub_renderer.render(pages, epub_path)

    assert epub_path.exists()
    with zipfile.ZipFile(epub_path) as zf:
        # Check that watermark text appears in a chapter
        for name in zf.namelist():
            if name.startswith("chapter_") and name.endswith(".xhtml"):
                content = zf.read(name).decode()
                assert "DRAFT" in content
                break


def test_epub_local_time(
    html_pages,
    sample_branding_config: Path,
    tmp_output: Path,
) -> None:
    pages, mkdocs_cfg = html_pages
    branding = load_config(sample_branding_config)

    epub_path = tmp_output / "local_time.epub"
    epub_renderer = EpubRenderer(branding, None, mkdocs_cfg)
    epub_renderer.render(pages, epub_path, local_time=True)

    assert epub_path.exists()
