"""Render Material for MkDocs annotations as footnote-style references."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from bs4 import BeautifulSoup, NavigableString, Tag
from bs4.element import AttributeValueList

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

_MARKER_RE = re.compile(r"\((\d+)\)")


def _find_annotate_blocks(soup: BeautifulSoup) -> list[tuple[Tag, Tag]]:
    """Find elements with class 'annotate' that have a next-sibling <ol>."""
    pairs: list[tuple[Tag, Tag]] = []
    for el in soup.find_all(class_="annotate"):
        # Walk next siblings, skipping whitespace NavigableStrings
        sibling = el.next_sibling
        while sibling is not None and isinstance(sibling, NavigableString):
            sibling = sibling.next_sibling
        if sibling is not None and isinstance(sibling, Tag) and sibling.name == "ol":
            pairs.append((el, sibling))
    return pairs


def _replace_markers(element: Tag, soup: BeautifulSoup) -> None:
    """Replace (N) text markers with <sup> tags inside an annotated element."""
    # Collect text nodes that contain markers — snapshot to avoid mutation issues
    text_nodes: list[NavigableString] = []
    for node in element.descendants:
        if isinstance(node, NavigableString) and _MARKER_RE.search(str(node)):
            # Skip text inside <code> or <pre> elements
            if node.parent and node.parent.name in ("code", "pre"):
                continue
            text_nodes.append(node)

    for text_node in text_nodes:
        text = str(text_node)
        parts = _MARKER_RE.split(text)
        if len(parts) <= 1:
            continue

        # Build replacement fragments: alternating text and <sup> tags
        # parts = ['before', '1', 'between', '2', 'after'] for "(1) ... (2)"
        parent = text_node.parent
        if parent is None:
            continue

        fragments: list[NavigableString | Tag] = []
        for i, part in enumerate(parts):
            if i % 2 == 0:
                # Regular text
                if part:
                    fragments.append(NavigableString(part))
            else:
                # Captured digit — create <sup>
                sup = soup.new_tag("sup")
                sup.attrs["class"] = AttributeValueList(["annotation-ref"])
                sup.string = part
                fragments.append(sup)

        # Replace the original text node with the fragments
        for frag in reversed(fragments):
            text_node.insert_after(frag)
        text_node.extract()


def _build_annotation_block(ol: Tag, soup: BeautifulSoup) -> Tag:
    """Convert an <ol> annotation list to a styled <div> block."""
    block = soup.new_tag("div")
    block.attrs["class"] = AttributeValueList(["annotation-list"])

    for i, li in enumerate(ol.find_all("li", recursive=False), start=1):
        p = soup.new_tag("p")
        p.attrs["class"] = AttributeValueList(["annotation-item"])

        # Add superscript number
        sup = soup.new_tag("sup")
        sup.string = str(i)
        p.append(sup)
        p.append(NavigableString(" "))

        # Move all children from the <li> into the <p>, preserving rich content
        for child in list(li.children):
            child.extract()
            p.append(child)

        block.append(p)

    return block


def render_annotations(html: str) -> str:
    """Transform Material for MkDocs annotation blocks into footnote-style HTML.

    Finds elements with class ``annotate`` paired with a sibling ``<ol>``,
    replaces ``(N)`` markers with ``<sup>`` references, and converts the
    list into a styled annotation block.
    """
    soup = BeautifulSoup(html, "lxml")
    pairs = _find_annotate_blocks(soup)

    if not pairs:
        return html

    for element, ol in pairs:
        _replace_markers(element, soup)
        annotation_block = _build_annotation_block(ol, soup)
        ol.replace_with(annotation_block)

        # Remove 'annotate' class, preserve others
        classes = list(element.get("class") or [])
        if "annotate" in classes:
            classes.remove("annotate")
        if classes:
            element.attrs["class"] = AttributeValueList(classes)
        else:
            del element.attrs["class"]

    # Return inner content of <body> to avoid lxml wrapper tags
    body = soup.find("body")
    if body:
        return body.decode_contents()
    return str(soup)
