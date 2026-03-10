"""Tests for PDF renderer."""

from pathlib import Path

from leafpress.config import load_config
from leafpress.git_info import extract_git_info
from leafpress.markdown_renderer import MarkdownRenderer
from leafpress.mkdocs_parser import NavItem, flatten_nav, parse_mkdocs_config
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
        html = renderer.render(md_file.read_text(), md_file)
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
        html = renderer.render(md_file.read_text(), md_file)
        html_pages.append((item, html))

    pdf_path = tmp_output / "no_branding.pdf"
    pdf_renderer = PdfRenderer(None, None, mkdocs_cfg)
    pdf_renderer.render(html_pages, pdf_path, cover_page=False, include_toc=False)

    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 0
