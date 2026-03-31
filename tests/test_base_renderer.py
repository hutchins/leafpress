"""Tests for base_renderer shared helpers."""

from __future__ import annotations

from pathlib import Path

from leafpress.base_renderer import make_anchor_id, replace_checkboxes, resolve_logo_uri

# --- replace_checkboxes ---


class TestReplaceCheckboxes:
    def test_checked_checkbox_replaced(self) -> None:
        html = (
            '<label class="task-list-control">'
            '<input type="checkbox" disabled checked/>'
            '<span class="task-list-indicator"></span>'
            "</label> Done"
        )
        result = replace_checkboxes(html)
        assert "&#x2611;" in result
        assert "task-checkbox checked" in result
        assert "<input" not in result

    def test_unchecked_checkbox_replaced(self) -> None:
        html = (
            '<label class="task-list-control">'
            '<input type="checkbox" disabled/>'
            '<span class="task-list-indicator"></span>'
            "</label> Todo"
        )
        result = replace_checkboxes(html)
        assert "&#x2610;" in result
        assert "task-checkbox" in result
        assert "<input" not in result

    def test_both_checkboxes_in_same_html(self) -> None:
        html = (
            '<label class="task-list-control">'
            '<input type="checkbox" disabled checked/>'
            '<span class="task-list-indicator"></span>'
            "</label> Done\n"
            '<label class="task-list-control">'
            '<input type="checkbox" disabled/>'
            '<span class="task-list-indicator"></span>'
            "</label> Todo"
        )
        result = replace_checkboxes(html)
        assert "&#x2611;" in result
        assert "&#x2610;" in result
        assert "<input" not in result

    def test_no_checkboxes_unchanged(self) -> None:
        html = "<p>Hello world</p>"
        assert replace_checkboxes(html) == html

    def test_empty_string(self) -> None:
        assert replace_checkboxes("") == ""


# --- make_anchor_id ---


class TestMakeAnchorId:
    def test_simple_title(self) -> None:
        assert make_anchor_id("Getting Started") == "getting-started"

    def test_special_characters_removed(self) -> None:
        assert make_anchor_id("What's New?") == "whats-new"

    def test_multiple_spaces_collapsed(self) -> None:
        assert make_anchor_id("Hello   World") == "hello-world"

    def test_leading_trailing_dashes_stripped(self) -> None:
        assert make_anchor_id(" -Hello- ") == "hello"

    def test_numbers_preserved(self) -> None:
        assert make_anchor_id("Step 1: Setup") == "step-1-setup"

    def test_unicode_letters_preserved(self) -> None:
        # \w matches unicode word chars
        result = make_anchor_id("Über Cool")
        assert "ber" in result

    def test_empty_string(self) -> None:
        assert make_anchor_id("") == ""


# --- resolve_logo_uri ---


class TestResolveLogoUri:
    def test_none_branding(self) -> None:
        assert resolve_logo_uri(None) == ""

    def test_no_logo_path(self) -> None:
        """Branding with empty logo_path returns empty string."""
        from leafpress.config import BrandingConfig

        branding = BrandingConfig(project_name="Test", company_name="Co", logo_path="")
        assert resolve_logo_uri(branding) == ""

    def test_http_url_returned_as_is(self) -> None:
        from leafpress.config import BrandingConfig

        branding = BrandingConfig(
            project_name="Test",
            company_name="Co",
            logo_path="https://example.com/logo.png",
        )
        assert resolve_logo_uri(branding) == "https://example.com/logo.png"

    def test_https_url_returned_as_is(self) -> None:
        from leafpress.config import BrandingConfig

        branding = BrandingConfig(
            project_name="Test",
            company_name="Co",
            logo_path="https://cdn.example.com/logo.svg",
        )
        assert resolve_logo_uri(branding) == "https://cdn.example.com/logo.svg"

    def test_local_path_converted_to_file_uri(self, tmp_path: Path) -> None:
        from leafpress.config import BrandingConfig

        logo = tmp_path / "logo.png"
        logo.write_bytes(b"fake png")
        branding = BrandingConfig(
            project_name="Test",
            company_name="Co",
            logo_path=str(logo),
        )
        result = resolve_logo_uri(branding)
        assert result.startswith("file://")
        assert "logo.png" in result
