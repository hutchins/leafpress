"""Tests for ODT renderer."""

from pathlib import Path

from leafpress.config import load_config
from leafpress.git_info import extract_git_info
from leafpress.markdown_renderer import MarkdownRenderer
from leafpress.mkdocs_parser import flatten_nav, parse_mkdocs_config
from leafpress.odt.renderer import OdtRenderer


def test_odt_generation(
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

    odt_path = tmp_output / "test.odt"
    odt_renderer = OdtRenderer(branding, git_info, mkdocs_cfg)
    odt_renderer.render(html_pages, odt_path)

    assert odt_path.exists()
    assert odt_path.stat().st_size > 0


def test_odt_without_branding(
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

    odt_path = tmp_output / "no_branding.odt"
    odt_renderer = OdtRenderer(None, None, mkdocs_cfg)
    odt_renderer.render(html_pages, odt_path, cover_page=False, include_toc=False)

    assert odt_path.exists()
    assert odt_path.stat().st_size > 0
