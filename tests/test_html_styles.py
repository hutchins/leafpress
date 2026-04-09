"""Tests for HTML CSS generation."""

from leafpress.config import BrandingConfig
from leafpress.html.styles import generate_html_css


def _make_branding(
    primary_color: str = "#1a73e8",
    accent_color: str = "#ffffff",
) -> BrandingConfig:
    return BrandingConfig(
        company_name="TestCo",
        project_name="TestProject",
        primary_color=primary_color,
        accent_color=accent_color,
    )


def test_generate_css_with_branding() -> None:
    branding = _make_branding(primary_color="#2e7d32", accent_color="#e8f5e9")
    css = generate_html_css(branding)

    assert "--lp-primary: #2e7d32" in css
    assert "--lp-accent: #e8f5e9" in css
    assert ".lp-sidebar" in css
    assert ".lp-cover" in css
    assert ".lp-footer" in css


def test_generate_css_without_branding() -> None:
    css = generate_html_css(None)

    # Falls back to default colors
    assert "--lp-primary: #1a73e8" in css
    assert "--lp-accent: #ffffff" in css


def test_css_has_print_styles() -> None:
    css = generate_html_css(None)
    assert "@media print" in css
    assert "display: none" in css  # sidebar hidden in print


def test_css_has_syntax_highlighting() -> None:
    css = generate_html_css(None)
    assert ".highlight" in css


def test_css_has_admonition_styles() -> None:
    css = generate_html_css(None)
    assert ".admonition" in css
    assert ".admonition.note" in css
    assert ".admonition.warning" in css
    assert ".admonition.tip" in css


def test_css_has_table_styles() -> None:
    css = generate_html_css(None)
    assert "border-collapse" in css
    assert "th" in css


def test_css_has_code_styles() -> None:
    css = generate_html_css(None)
    assert "Courier New" in css or "monospace" in css
    assert "pre" in css


def test_css_has_task_list_styles() -> None:
    css = generate_html_css(None)
    assert ".task-list" in css
    assert ".task-checkbox" in css
