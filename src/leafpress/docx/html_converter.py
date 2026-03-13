"""Convert HTML fragments to python-docx document elements."""

from __future__ import annotations

import logging
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag
from docx import Document
from docx.enum.text import WD_COLOR_INDEX
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

logger = logging.getLogger(__name__)


class HtmlToDocxConverter:
    """Converts HTML fragments into python-docx document elements."""

    def __init__(self, doc: Document, docs_dir: Path) -> None:
        self._doc = doc
        self._docs_dir = docs_dir

    def convert(self, html: str) -> None:
        """Convert an HTML fragment and append to the document."""
        if not html.strip():
            return

        soup = BeautifulSoup(html, "lxml")
        body = soup.find("body")
        if body is None:
            body = soup

        for element in body.children:
            if isinstance(element, Tag):
                self._process_element(element)

    def _process_element(self, element: Tag) -> None:
        """Dispatch an HTML element to the appropriate handler."""
        tag = element.name
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._handle_heading(element)
        elif tag == "p":
            self._handle_paragraph(element)
        elif tag in ("ul", "ol"):
            self._handle_list(element, ordered=(tag == "ol"))
        elif tag == "table":
            self._handle_table(element)
        elif tag == "pre":
            self._handle_code_block(element)
        elif tag == "div" and "admonition" in element.get("class", []):
            self._handle_admonition(element)
        elif tag == "img":
            self._handle_image(element)
        elif tag == "blockquote":
            self._handle_blockquote(element)
        elif tag == "hr":
            self._handle_horizontal_rule()
        elif tag == "dl":
            self._handle_definition_list(element)
        elif tag == "details":
            self._handle_details(element)
        elif tag in ("div", "section", "article"):
            for child in element.children:
                if isinstance(child, Tag):
                    self._process_element(child)

    def _handle_heading(self, element: Tag) -> None:
        """Convert heading tags to DOCX headings."""
        level = int(element.name[1])
        text = element.get_text(strip=True)
        self._doc.add_heading(text, level=min(level, 4))

    def _handle_paragraph(self, element: Tag) -> None:
        """Convert paragraph tags to DOCX paragraphs with inline formatting."""
        para = self._doc.add_paragraph()
        self._add_inline_content(para, element)

    def _handle_list(self, element: Tag, ordered: bool, level: int = 0) -> None:
        """Convert list tags to DOCX list items."""
        for _i, li in enumerate(element.find_all("li", recursive=False)):
            is_task_item = "task-list-item" in li.get("class", [])

            if is_task_item:
                para = self._doc.add_paragraph()
                para.paragraph_format.left_indent = Pt(18 * level)
                # Determine checked state from the checkbox input
                checkbox = li.find("input", attrs={"type": "checkbox"})
                if checkbox and checkbox.get("checked") is not None:
                    run = para.add_run("\u2611 ")  # ☑
                    run.font.color.rgb = RGBColor(0x00, 0xC8, 0x53)
                else:
                    run = para.add_run("\u2610 ")  # ☐
                    run.font.color.rgb = RGBColor(0x99, 0x99, 0x99)
                # Add remaining text content (skip the label/input elements)
                self._add_inline_content(para, li, skip_nested_lists=True, skip_task_controls=True)
            else:
                style = "List Number" if ordered else "List Bullet"
                para = self._doc.add_paragraph(style=style)
                para.paragraph_format.left_indent = Pt(18 * level)
                self._add_inline_content(para, li, skip_nested_lists=True)

            # Handle nested lists
            for nested in li.find_all(["ul", "ol"], recursive=False):
                self._handle_list(nested, ordered=(nested.name == "ol"), level=level + 1)

    def _handle_table(self, element: Tag) -> None:
        """Convert HTML tables to DOCX tables."""
        rows = element.find_all("tr")
        if not rows:
            return

        # Determine column count from first row
        first_row = rows[0]
        cols = first_row.find_all(["th", "td"])
        if not cols:
            return

        table = self._doc.add_table(rows=len(rows), cols=len(cols))
        table.style = "Table Grid"

        for row_idx, tr in enumerate(rows):
            cells = tr.find_all(["th", "td"])
            for col_idx, cell in enumerate(cells):
                if col_idx < len(table.columns):
                    table_cell = table.cell(row_idx, col_idx)
                    table_cell.text = cell.get_text(strip=True)

                    # Bold header cells
                    if cell.name == "th":
                        for paragraph in table_cell.paragraphs:
                            for run in paragraph.runs:
                                run.bold = True

    def _handle_code_block(self, element: Tag) -> None:
        """Convert pre/code blocks to styled DOCX paragraphs."""
        code_text = element.get_text()
        para = self._doc.add_paragraph()
        run = para.add_run(code_text)
        run.font.name = "Courier New"
        run.font.size = Pt(9)

        # Light gray background via shading
        p_pr = para._element.get_or_add_pPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"), "F5F5F5")
        p_pr.append(shd)

        para.paragraph_format.space_before = Pt(6)
        para.paragraph_format.space_after = Pt(6)

    def _handle_admonition(self, element: Tag) -> None:
        """Convert admonition divs to styled DOCX paragraphs."""
        title_el = element.find(class_="admonition-title")
        title_text = title_el.get_text(strip=True) if title_el else "Note"

        # Determine admonition type for color
        classes = element.get("class", [])
        color = self._admonition_color(classes)

        # Title paragraph
        title_para = self._doc.add_paragraph()
        title_run = title_para.add_run(title_text)
        title_run.bold = True
        title_run.font.color.rgb = color
        title_para.paragraph_format.space_before = Pt(12)

        # Add left border to title
        self._add_left_border(title_para, color)

        # Content paragraphs
        for child in element.children:
            if (
                isinstance(child, Tag)
                and "admonition-title" not in child.get("class", [])
                and child.name == "p"
            ):
                para = self._doc.add_paragraph()
                self._add_inline_content(para, child)
                para.paragraph_format.left_indent = Pt(18)
                self._add_left_border(para, color)

    def _handle_image(self, element: Tag) -> None:
        """Insert an image into the document."""
        src = element.get("src", "")
        if not src:
            return

        # Resolve file:// URIs back to paths
        if src.startswith("file://"):
            image_path = Path(src.removeprefix("file://"))
        else:
            image_path = self._docs_dir / src

        if image_path.exists():
            try:
                self._doc.add_picture(str(image_path), width=Inches(5.5))
            except Exception as exc:
                logger.warning("Could not embed image %r: %s", src, exc)
                para = self._doc.add_paragraph()
                para.add_run(f"[Image: {src}]").italic = True
        else:
            para = self._doc.add_paragraph()
            para.add_run(f"[Image not found: {src}]").italic = True

    def _handle_blockquote(self, element: Tag) -> None:
        """Convert blockquotes to indented paragraphs."""
        para = self._doc.add_paragraph()
        para.paragraph_format.left_indent = Pt(36)
        self._add_inline_content(para, element)
        for run in para.runs:
            run.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
            run.italic = True

    def _handle_horizontal_rule(self) -> None:
        """Add a horizontal rule as a paragraph border."""
        para = self._doc.add_paragraph()
        p_pr = para._element.get_or_add_pPr()
        p_bdr = OxmlElement("w:pBdr")
        bottom = OxmlElement("w:bottom")
        bottom.set(qn("w:val"), "single")
        bottom.set(qn("w:sz"), "6")
        bottom.set(qn("w:space"), "1")
        bottom.set(qn("w:color"), "E0E0E0")
        p_bdr.append(bottom)
        p_pr.append(p_bdr)

    def _add_inline_content(
        self,
        para: object,
        element: Tag,
        skip_nested_lists: bool = False,
        skip_task_controls: bool = False,
    ) -> None:
        """Add inline content (bold, italic, code, links) to a paragraph."""
        for child in element.children:
            if isinstance(child, NavigableString):
                text = str(child)
                if text.strip():
                    para.add_run(text)  # type: ignore[union-attr]
            elif isinstance(child, Tag):
                if skip_nested_lists and child.name in ("ul", "ol"):
                    continue
                # Skip task-list label/input elements (already handled)
                if skip_task_controls and (
                    child.name == "label"
                    or (child.name == "input" and child.get("type") == "checkbox")
                ):
                    continue
                if child.name in ("strong", "b"):
                    run = para.add_run(child.get_text())  # type: ignore[union-attr]
                    run.bold = True
                elif child.name in ("em", "i"):
                    run = para.add_run(child.get_text())  # type: ignore[union-attr]
                    run.italic = True
                elif child.name in ("code", "kbd"):
                    run = para.add_run(child.get_text())  # type: ignore[union-attr]
                    run.font.name = "Courier New"
                    run.font.size = Pt(9)
                elif child.name == "a":
                    run = para.add_run(child.get_text())  # type: ignore[union-attr]
                    run.font.color.rgb = RGBColor(0x1A, 0x73, 0xE8)
                    run.underline = True
                elif child.name == "del":
                    before = len(para.runs)  # type: ignore[union-attr]
                    self._add_inline_content(para, child, skip_nested_lists, skip_task_controls)
                    for run in para.runs[before:]:  # type: ignore[union-attr]
                        run.font.strike = True
                elif child.name == "sup":
                    run = para.add_run(child.get_text())  # type: ignore[union-attr]
                    run.font.superscript = True
                elif child.name == "sub":
                    run = para.add_run(child.get_text())  # type: ignore[union-attr]
                    run.font.subscript = True
                elif child.name == "mark":
                    run = para.add_run(child.get_text())  # type: ignore[union-attr]
                    run.font.highlight_color = WD_COLOR_INDEX.YELLOW
                elif child.name == "br":
                    para.add_run("\n")  # type: ignore[union-attr]
                elif child.name == "img" and any(
                    c in child.get("class", []) for c in ("emojione", "twemoji", "gemoji")
                ):
                    alt = child.get("alt", "")
                    if alt:
                        para.add_run(alt)  # type: ignore[union-attr]
                elif child.name == "img":
                    self._handle_image(child)
                else:
                    # Recurse for other inline elements (span, abbr, etc.)
                    self._add_inline_content(para, child, skip_nested_lists, skip_task_controls)

    def _handle_details(self, element: Tag) -> None:
        """Render <details>/<summary> as a bold label followed by content."""
        summary = element.find("summary")
        if summary:
            para = self._doc.add_paragraph()
            run = para.add_run(summary.get_text(strip=True))
            run.bold = True
        for child in element.children:
            if isinstance(child, Tag) and child.name != "summary":
                self._process_element(child)

    def _handle_definition_list(self, element: Tag) -> None:
        """Render <dl>/<dt>/<dd> as bold terms with indented definitions."""
        for child in element.children:
            if not isinstance(child, Tag):
                continue
            if child.name == "dt":
                para = self._doc.add_paragraph()
                run = para.add_run(child.get_text(strip=True))
                run.bold = True
            elif child.name == "dd":
                para = self._doc.add_paragraph()
                para.paragraph_format.left_indent = Pt(36)
                self._add_inline_content(para, child)

    def _admonition_color(self, classes: list[str]) -> RGBColor:
        """Get the border color for an admonition type."""
        color_map = {
            "note": RGBColor(0x44, 0x8A, 0xFF),
            "warning": RGBColor(0xFF, 0x91, 0x00),
            "danger": RGBColor(0xFF, 0x17, 0x44),
            "error": RGBColor(0xFF, 0x17, 0x44),
            "tip": RGBColor(0x00, 0xC8, 0x53),
            "hint": RGBColor(0x00, 0xC8, 0x53),
            "info": RGBColor(0x21, 0x96, 0xF3),
            "example": RGBColor(0x7C, 0x4D, 0xFF),
        }
        for cls in classes:
            if cls in color_map:
                return color_map[cls]
        return RGBColor(0x44, 0x8A, 0xFF)

    def _add_left_border(self, para: object, color: RGBColor) -> None:
        """Add a colored left border to a paragraph."""
        p_pr = para._element.get_or_add_pPr()  # type: ignore[union-attr]
        p_bdr = OxmlElement("w:pBdr")
        left = OxmlElement("w:left")
        left.set(qn("w:val"), "single")
        left.set(qn("w:sz"), "18")
        left.set(qn("w:space"), "4")
        hex_color = f"{color[0]:02X}{color[1]:02X}{color[2]:02X}"
        left.set(qn("w:color"), hex_color)
        p_bdr.append(left)
        p_pr.append(p_bdr)
