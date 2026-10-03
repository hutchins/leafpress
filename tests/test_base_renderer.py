"""Tests for base_renderer shared helpers."""

from __future__ import annotations

import pytest

from leafpress.base_renderer import make_anchor_id, replace_checkboxes

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

    @pytest.mark.parametrize(
        ("html", "checked"),
        [
            # Plain pymdownx.tasklist output (no custom_checkbox wrapper)
            ('<li class="task-list-item"><input type="checkbox" disabled checked> x</li>', True),
            ('<li class="task-list-item"><input type="checkbox" disabled> x</li>', False),
            # Re-serialized by the HTML sanitizer
            (
                '<label class="task-list-control"><input type="checkbox" disabled="" '
                'checked=""><span class="task-list-indicator"></span></label> x',
                True,
            ),
            (
                '<label class="task-list-control"><input type="checkbox" disabled="">'
                '<span class="task-list-indicator"></span></label> x',
                False,
            ),
            ("<input checked type='checkbox'> x", True),
        ],
    )
    def test_serialization_variants(self, html: str, checked: bool) -> None:
        result = replace_checkboxes(html)
        assert "<input" not in result
        assert "task-list-control" not in result
        assert ("&#x2611;" in result) is checked
        assert ("&#x2610;" in result) is not checked

    def test_radio_inputs_untouched(self) -> None:
        html = '<input type="radio" name="t" checked>'
        assert replace_checkboxes(html) == html

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
