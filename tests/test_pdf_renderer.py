"""Tests for PDF renderer."""

from pathlib import Path

import pytest
from leafpress.config import load_config
from leafpress.exceptions import RenderError
from leafpress.git_info import extract_git_info
from leafpress.markdown_renderer import MarkdownRenderer
from leafpress.mkdocs_parser import flatten_nav, parse_mkdocs_config
from leafpress.pdf.renderer import PdfRenderer


def test_pdf_generation(
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

    pdf_path = tmp_output / "test.pdf"
    pdf_renderer = PdfRenderer(branding, git_info, mkdocs_cfg)
    pdf_renderer.render(html_pages, pdf_path)

    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 0


def test_pdf_without_branding(
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

    pdf_path = tmp_output / "no_branding.pdf"
    pdf_renderer = PdfRenderer(None, None, mkdocs_cfg)
    pdf_renderer.render(html_pages, pdf_path, cover_page=False, include_toc=False)

    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 0


# --- _format_pdf_error ---


class _FakeUnrecognizedImageError(Exception):
    """Simulate WeasyPrint's UnrecognizedImageError."""

    pass


_FakeUnrecognizedImageError.__name__ = "UnrecognizedImageError"


def test_format_pdf_error_unrecognized_image() -> None:
    exc = _FakeUnrecognizedImageError("bad image data")
    msg = PdfRenderer._format_pdf_error(exc)
    assert "unrecognized image format" in msg
    assert "librsvg" in msg
    assert "brew install" in msg
    assert "apt install" in msg
    assert "leafpress doctor" in msg


def test_format_pdf_error_generic_image_error() -> None:
    exc = ValueError("Failed to load image at /path/to/broken.png")
    msg = PdfRenderer._format_pdf_error(exc)
    assert "image error" in msg
    assert "PNG, JPEG" in msg
    assert "leafpress doctor" in msg


def test_format_pdf_error_non_image_error() -> None:
    exc = RuntimeError("something completely different")
    msg = PdfRenderer._format_pdf_error(exc)
    assert "PDF rendering failed" in msg
    assert "RuntimeError" in msg
    assert "something completely different" in msg
    assert "leafpress doctor" in msg


def test_pdf_render_wraps_exception_as_render_error(
    sample_mkdocs_config: Path,
    tmp_output: Path,
) -> None:
    """Verify that write_pdf errors are wrapped as RenderError."""
    from unittest.mock import patch

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

    pdf_path = tmp_output / "fail.pdf"
    pdf_renderer = PdfRenderer(None, None, mkdocs_cfg)

    with (
        patch("weasyprint.HTML.write_pdf", side_effect=_FakeUnrecognizedImageError("bad")),
        pytest.raises(RenderError, match="unrecognized image format"),
    ):
        pdf_renderer.render(html_pages, pdf_path, cover_page=False, include_toc=False)
