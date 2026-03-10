"""Tests for PDF CSS generation."""

from datetime import datetime, timezone

from leafpress.config import BrandingConfig
from leafpress.git_info import GitVersion
from leafpress.pdf.styles import generate_pdf_css


def _make_branding(**kwargs: object) -> BrandingConfig:
    defaults = {"company_name": "TestCo", "project_name": "TestProject"}
    defaults.update(kwargs)
    return BrandingConfig(**defaults)


def _make_git_info(**kwargs: object) -> GitVersion:
    defaults = {
        "branch": "main",
        "commit_hash": "abc1234",
        "commit_hash_full": "abc1234567890abcdef1234567890abcdef123456",
        "commit_date": datetime(2025, 1, 15, tzinfo=timezone.utc),
        "is_dirty": False,
        "tag": "v1.0.0",
        "tag_distance": 0,
    }
    defaults.update(kwargs)
    return GitVersion(**defaults)


def test_generate_css_with_branding() -> None:
    branding = _make_branding()
    git_info = _make_git_info()
    css = generate_pdf_css(branding, git_info)

    assert "@page" in css
    assert "TestCo" in css
    assert "TestProject" in css
    assert "v1.0.0" in css
    assert "abc1234" in css
    assert "LeafPress" in css


def test_generate_css_without_branding() -> None:
    css = generate_pdf_css(None, None)
    assert "@page" in css
    assert "LeafPress" in css


def test_generate_css_without_git_info() -> None:
    branding = _make_branding()
    css = generate_pdf_css(branding, None)
    assert "TestCo" in css
    assert "@page" in css


def test_page_size_from_branding() -> None:
    branding = _make_branding()
    branding.pdf.page_size = "Letter"
    css = generate_pdf_css(branding, None)
    assert "Letter" in css


def test_custom_margins() -> None:
    branding = _make_branding()
    branding.pdf.margin_top = "30mm"
    css = generate_pdf_css(branding, None)
    assert "30mm" in css


def test_color_overrides() -> None:
    branding = _make_branding(primary_color="#ff0000")
    css = generate_pdf_css(branding, None)
    assert "#ff0000" in css


def test_no_color_overrides_without_branding() -> None:
    css = generate_pdf_css(None, None)
    # No brand color overrides section when branding is None
    assert "Brand color overrides" not in css


def test_footer_custom_text() -> None:
    branding = _make_branding()
    branding.footer.custom_text = "Confidential"
    css = generate_pdf_css(branding, _make_git_info())
    assert "Confidential" in css


def test_footer_branch_included() -> None:
    branding = _make_branding()
    branding.footer.include_branch = True
    css = generate_pdf_css(branding, _make_git_info())
    assert "main" in css


def test_footer_tag_with_distance() -> None:
    git_info = _make_git_info(tag="v1.0.0", tag_distance=3)
    css = generate_pdf_css(None, git_info)
    assert "v1.0.0+3" in css


def test_first_page_no_headers() -> None:
    css = generate_pdf_css(_make_branding(), _make_git_info())
    assert "@page :first" in css
    assert "content: none" in css
