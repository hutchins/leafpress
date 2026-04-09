"""Tests for DOCX renderer."""

from pathlib import Path

import pytest

from leafpress.config import WatermarkConfig, load_config
from leafpress.docx.renderer import DocxRenderer
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


def test_docx_generation(
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

    docx_path = tmp_output / "test.docx"
    docx_renderer = DocxRenderer(branding, git_info, mkdocs_cfg)
    docx_renderer.render(html_pages, docx_path)

    assert docx_path.exists()
    assert docx_path.stat().st_size > 0


def test_docx_without_branding(html_pages, tmp_output: Path) -> None:
    pages, mkdocs_cfg = html_pages
    docx_path = tmp_output / "no_branding.docx"
    docx_renderer = DocxRenderer(None, None, mkdocs_cfg)
    docx_renderer.render(pages, docx_path, cover_page=False, include_toc=False)

    assert docx_path.exists()
    assert docx_path.stat().st_size > 0


def test_docx_with_watermark(
    html_pages,
    sample_branding_config: Path,
    tmp_output: Path,
) -> None:
    pages, mkdocs_cfg = html_pages
    branding = load_config(sample_branding_config)
    branding.watermark = WatermarkConfig(text="CONFIDENTIAL")
    git_info = extract_git_info(sample_branding_config.parent)

    docx_path = tmp_output / "watermark.docx"
    docx_renderer = DocxRenderer(branding, git_info, mkdocs_cfg)
    docx_renderer.render(pages, docx_path)

    assert docx_path.exists()
    assert docx_path.stat().st_size > 0


def test_docx_no_cover_page(
    html_pages,
    sample_branding_config: Path,
    tmp_output: Path,
) -> None:
    pages, mkdocs_cfg = html_pages
    branding = load_config(sample_branding_config)

    docx_path = tmp_output / "no_cover.docx"
    docx_renderer = DocxRenderer(branding, None, mkdocs_cfg)
    docx_renderer.render(pages, docx_path, cover_page=False)

    assert docx_path.exists()


def test_docx_no_toc(
    html_pages,
    sample_branding_config: Path,
    tmp_output: Path,
) -> None:
    pages, mkdocs_cfg = html_pages
    branding = load_config(sample_branding_config)

    docx_path = tmp_output / "no_toc.docx"
    docx_renderer = DocxRenderer(branding, None, mkdocs_cfg)
    docx_renderer.render(pages, docx_path, include_toc=False)

    assert docx_path.exists()


def test_docx_local_time(
    html_pages,
    sample_branding_config: Path,
    tmp_output: Path,
) -> None:
    pages, mkdocs_cfg = html_pages
    branding = load_config(sample_branding_config)

    docx_path = tmp_output / "local_time.docx"
    docx_renderer = DocxRenderer(branding, None, mkdocs_cfg)
    docx_renderer.render(pages, docx_path, local_time=True)

    assert docx_path.exists()


# --- _is_svg ---


class TestIsSvg:
    def test_svg_extension(self) -> None:
        assert DocxRenderer._is_svg("assets/logo.svg") is True

    def test_svg_uppercase(self) -> None:
        assert DocxRenderer._is_svg("assets/Logo.SVG") is True

    def test_png_not_svg(self) -> None:
        assert DocxRenderer._is_svg("assets/logo.png") is False

    def test_svg_url(self) -> None:
        assert DocxRenderer._is_svg("https://example.com/logo.svg") is True

    def test_svg_url_with_query(self) -> None:
        assert DocxRenderer._is_svg("https://example.com/logo.svg?v=2") is True

    def test_svg_url_with_fragment(self) -> None:
        assert DocxRenderer._is_svg("https://example.com/logo.svg#layer1") is True

    def test_non_svg_url(self) -> None:
        assert DocxRenderer._is_svg("https://example.com/logo.png") is False


# --- SVG logo skip ---


def test_docx_svg_logo_skipped_with_warning(
    html_pages,
    sample_branding_config: Path,
    tmp_output: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """SVG logo_path should be skipped with a warning, not crash."""
    import logging

    pages, mkdocs_cfg = html_pages
    branding = load_config(sample_branding_config)
    branding.logo_path = "assets/logo.svg"

    docx_path = tmp_output / "svg_skip.docx"
    docx_renderer = DocxRenderer(branding, None, mkdocs_cfg)

    with caplog.at_level(logging.WARNING):
        docx_renderer.render(pages, docx_path)

    assert docx_path.exists()
    assert any("SVG logos are not supported in DOCX" in r.message for r in caplog.records)
