"""Tests for HTML renderer."""

from pathlib import Path

from leafpress.config import load_config
from leafpress.git_info import extract_git_info
from leafpress.html.renderer import HtmlRenderer
from leafpress.markdown_renderer import MarkdownRenderer
from leafpress.mkdocs_parser import flatten_nav, parse_mkdocs_config


def test_html_generation(
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

    html_path = tmp_output / "test.html"
    html_renderer = HtmlRenderer(branding, git_info, mkdocs_cfg)
    html_renderer.render(html_pages, html_path)

    assert html_path.exists()
    assert html_path.stat().st_size > 0

    content = html_path.read_text()
    assert "<!DOCTYPE html>" in content
    assert "LeafPress" in content
    assert "<style>" in content


def test_html_without_branding(
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

    html_path = tmp_output / "no_branding.html"
    html_renderer = HtmlRenderer(None, None, mkdocs_cfg)
    html_renderer.render(html_pages, html_path, cover_page=False, include_toc=False)

    assert html_path.exists()
    assert html_path.stat().st_size > 0
    content = html_path.read_text()
    assert "<!DOCTYPE html>" in content
