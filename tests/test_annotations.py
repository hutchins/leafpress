"""Tests for Material for MkDocs annotation rendering."""

from __future__ import annotations

from unittest.mock import patch

from bs4 import BeautifulSoup

from leafpress.annotations import (
    _build_annotation_block,
    _find_annotate_blocks,
    _replace_markers,
    render_annotations,
)


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


# --- _find_annotate_blocks ---


def test_find_annotate_paragraph_with_ol() -> None:
    """Finds a <p class="annotate"> followed by an <ol>."""
    soup = _soup('<p class="annotate">Text (1)</p><ol><li>Note</li></ol>')
    pairs = _find_annotate_blocks(soup)
    assert len(pairs) == 1
    assert pairs[0][0].name == "p"
    assert pairs[0][1].name == "ol"


def test_find_annotate_ignores_without_ol() -> None:
    """Skips .annotate elements that have no sibling <ol>."""
    soup = _soup('<p class="annotate">Text (1)</p><p>Next</p>')
    pairs = _find_annotate_blocks(soup)
    assert len(pairs) == 0


def test_find_annotate_div() -> None:
    """Finds a <div class="annotate"> followed by an <ol>."""
    soup = _soup('<div class="annotate"><p>Text (1)</p></div><ol><li>Note</li></ol>')
    pairs = _find_annotate_blocks(soup)
    assert len(pairs) == 1
    assert pairs[0][0].name == "div"


def test_find_multiple_annotate_blocks() -> None:
    """Finds multiple independent annotate blocks."""
    soup = _soup(
        '<p class="annotate">A (1)</p><ol><li>Note A</li></ol>'
        '<p class="annotate">B (1)</p><ol><li>Note B</li></ol>'
    )
    pairs = _find_annotate_blocks(soup)
    assert len(pairs) == 2


def test_find_annotate_with_extra_classes() -> None:
    """Finds element with 'annotate' among multiple classes."""
    soup = _soup('<p class="custom annotate">Text (1)</p><ol><li>Note</li></ol>')
    pairs = _find_annotate_blocks(soup)
    assert len(pairs) == 1


def test_find_annotate_skips_whitespace_siblings() -> None:
    """Finds <ol> even with whitespace text nodes between."""
    soup = _soup('<p class="annotate">Text (1)</p>\n<ol><li>Note</li></ol>')
    pairs = _find_annotate_blocks(soup)
    assert len(pairs) == 1


# --- _replace_markers ---


def test_replace_single_marker() -> None:
    """Replaces a single (1) marker with <sup>."""
    soup = _soup('<p class="annotate">Hello (1) world</p>')
    element = soup.find("p")
    _replace_markers(element, soup)
    sups = element.find_all("sup", class_="annotation-ref")
    assert len(sups) == 1
    assert sups[0].string == "1"
    assert "Hello" in element.get_text()
    assert "world" in element.get_text()


def test_replace_multiple_markers() -> None:
    """Replaces (1) and (2) in the same text node."""
    soup = _soup('<p class="annotate">A (1) B (2) C</p>')
    element = soup.find("p")
    _replace_markers(element, soup)
    sups = element.find_all("sup", class_="annotation-ref")
    assert len(sups) == 2
    assert sups[0].string == "1"
    assert sups[1].string == "2"


def test_replace_no_markers_unchanged() -> None:
    """Element without markers is not modified."""
    soup = _soup('<p class="annotate">No markers here</p>')
    element = soup.find("p")
    original_text = element.get_text()
    _replace_markers(element, soup)
    assert element.get_text() == original_text
    assert element.find("sup") is None


def test_replace_ignores_non_digit_parens() -> None:
    """Parenthesized text like (abc) is not replaced."""
    soup = _soup('<p class="annotate">Call func(abc) here</p>')
    element = soup.find("p")
    _replace_markers(element, soup)
    assert element.find("sup") is None
    assert "(abc)" in element.get_text()


def test_replace_skips_markers_inside_code() -> None:
    """Markers inside <code> tags are left alone."""
    soup = _soup('<p class="annotate">See <code>func(1)</code> here (2)</p>')
    element = soup.find("p")
    _replace_markers(element, soup)
    sups = element.find_all("sup", class_="annotation-ref")
    # Only (2) should be replaced, not func(1) inside <code>
    assert len(sups) == 1
    assert sups[0].string == "2"
    assert "func(1)" in element.find("code").get_text()


# --- _build_annotation_block ---


def test_build_basic_annotation_block() -> None:
    """Converts <ol> with two items into styled annotation block."""
    soup = _soup("<ol><li>First note</li><li>Second note</li></ol>")
    ol = soup.find("ol")
    block = _build_annotation_block(ol, soup)
    assert block.name == "div"
    assert "annotation-list" in block.get("class", [])
    items = block.find_all("p", class_="annotation-item")
    assert len(items) == 2
    assert items[0].find("sup").string == "1"
    assert "First note" in items[0].get_text()
    assert items[1].find("sup").string == "2"
    assert "Second note" in items[1].get_text()


def test_build_annotation_with_emoji_img() -> None:
    """Preserves <img class="twemoji"> inside annotation items."""
    soup = _soup('<ol><li><img class="twemoji" alt="👋"> Hello</li></ol>')
    ol = soup.find("ol")
    block = _build_annotation_block(ol, soup)
    item = block.find("p", class_="annotation-item")
    img = item.find("img", class_="twemoji")
    assert img is not None
    assert img["alt"] == "👋"


def test_build_annotation_with_inline_formatting() -> None:
    """Preserves bold/code inside annotation items."""
    soup = _soup("<ol><li><strong>Important</strong> note with <code>code</code></li></ol>")
    ol = soup.find("ol")
    block = _build_annotation_block(ol, soup)
    item = block.find("p", class_="annotation-item")
    assert item.find("strong") is not None
    assert item.find("code") is not None


# --- render_annotations (integration) ---


def test_full_annotation_transform() -> None:
    """End-to-end: markers become <sup>, <ol> becomes annotation block."""
    html = (
        '<p class="annotate">Hello (1) world (2).</p>'
        "<ol><li>First annotation</li><li>Second annotation</li></ol>"
    )
    result = render_annotations(html)
    soup = _soup(result)
    # Markers replaced with <sup>
    sups_in_p = soup.find_all("sup", class_="annotation-ref")
    assert len(sups_in_p) == 2
    # <ol> replaced with annotation block
    assert soup.find("ol") is None
    block = soup.find("div", class_="annotation-list")
    assert block is not None
    items = block.find_all("p", class_="annotation-item")
    assert len(items) == 2


def test_no_annotations_returns_unchanged() -> None:
    """HTML without .annotate blocks passes through unchanged."""
    html = "<p>Normal paragraph</p><ol><li>List item</li></ol>"
    result = render_annotations(html)
    assert "<p>Normal paragraph</p>" in result
    assert "<ol>" in result


def test_annotate_without_ol_left_unchanged() -> None:
    """An .annotate element without a sibling <ol> is left alone."""
    html = '<p class="annotate">Text (1)</p><p>Other</p>'
    result = render_annotations(html)
    assert 'class="annotate"' in result
    assert "(1)" in result


def test_annotate_preserves_other_classes() -> None:
    """Other CSS classes on the element are preserved after processing."""
    html = '<p class="custom annotate extra">Text (1)</p><ol><li>Note</li></ol>'
    result = render_annotations(html)
    soup = _soup(result)
    p = soup.find("p")
    classes = p.get("class", [])
    assert "custom" in classes
    assert "extra" in classes
    assert "annotate" not in classes


def test_annotate_removes_class_attr_when_only_annotate() -> None:
    """class attribute is removed entirely when 'annotate' was the only class."""
    html = '<p class="annotate">Text (1)</p><ol><li>Note</li></ol>'
    result = render_annotations(html)
    soup = _soup(result)
    p = soup.find("p")
    # class attribute should be gone entirely
    assert p.get("class") is None


def test_multiple_independent_annotation_blocks() -> None:
    """Two separate annotation blocks are both processed."""
    html = (
        '<p class="annotate">First (1)</p><ol><li>Note A</li></ol>'
        '<p class="annotate">Second (1)</p><ol><li>Note B</li></ol>'
    )
    result = render_annotations(html)
    soup = _soup(result)
    blocks = soup.find_all("div", class_="annotation-list")
    assert len(blocks) == 2
    assert "Note A" in blocks[0].get_text()
    assert "Note B" in blocks[1].get_text()


# --- Pipeline integration ---


def test_markdown_renderer_calls_render_annotations() -> None:
    """MarkdownRenderer.render() calls render_annotations in the pipeline."""
    from pathlib import Path

    from leafpress.markdown_renderer import MarkdownRenderer

    renderer = MarkdownRenderer(extensions=[], docs_dir=Path("."))

    with patch("leafpress.annotations.render_annotations") as mock_render:
        mock_render.return_value = "<p>mocked</p>"
        renderer.render("# Hello", Path("test.md"))

    mock_render.assert_called_once()
