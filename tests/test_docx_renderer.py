"""Tests for DOCX renderer."""

from pathlib import Path

from leafpress.config import load_config
from leafpress.docx.renderer import DocxRenderer
from leafpress.git_info import extract_git_info
from leafpress.markdown_renderer import MarkdownRenderer
from leafpress.mkdocs_parser import flatten_nav, parse_mkdocs_config


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
        html = renderer.render(md_file.read_text(), md_file)
        html_pages.append((item, html))

    docx_path = tmp_output / "test.docx"
    docx_renderer = DocxRenderer(branding, git_info, mkdocs_cfg)
    docx_renderer.render(html_pages, docx_path)

    assert docx_path.exists()
    assert docx_path.stat().st_size > 0


def test_docx_without_branding(
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

    docx_path = tmp_output / "no_branding.docx"
    docx_renderer = DocxRenderer(None, None, mkdocs_cfg)
    docx_renderer.render(html_pages, docx_path, cover_page=False, include_toc=False)

    assert docx_path.exists()
    assert docx_path.stat().st_size > 0
