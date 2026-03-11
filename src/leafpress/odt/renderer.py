"""ODT (OpenDocument Text) generation using odfpy."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag
from odf.draw import Frame, Image
from odf.opendocument import OpenDocumentText
from odf.style import (
    FontFace,
    Footer,
    GraphicProperties,
    MasterPage,
    PageLayout,
    PageLayoutProperties,
    ParagraphProperties,
    Style,
    TableCellProperties,
    TableColumnProperties,
    TableProperties,
    TextProperties,
)
from odf.table import Table, TableCell, TableColumn, TableRow
from odf.text import H, P, Span

from leafpress.config import BrandingConfig
from leafpress.git_info import GitVersion
from leafpress.mkdocs_parser import MkDocsConfig, NavItem


class OdtRenderer:
    """Generates a single ODT file from HTML pages."""

    def __init__(
        self,
        branding: BrandingConfig | None,
        git_info: GitVersion | None,
        mkdocs_cfg: MkDocsConfig,
    ) -> None:
        self._branding = branding
        self._git_info = git_info
        self._mkdocs_cfg = mkdocs_cfg

    def render(
        self,
        html_pages: list[tuple[NavItem, str]],
        output_path: Path,
        cover_page: bool = True,
        include_toc: bool = True,
        local_time: bool = False,
    ) -> None:
        """Build an ODT document from converted HTML pages."""
        self._local_time = local_time
        doc = OpenDocumentText()
        self._setup_styles(doc)
        self._setup_page_layout(doc)
        self._add_watermark_style(doc)

        if cover_page:
            self._add_cover_page(doc)

        if include_toc:
            self._add_toc(doc, html_pages)

        for item, html_content in html_pages:
            if item.path is None:
                level = min(item.level + 1, 4)
                heading = H(outlinelevel=level, stylename=f"Heading {level}")
                heading.addText(item.title)
                doc.text.addElement(heading)
                continue
            self._convert_html(doc, html_content)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(output_path))

    def _setup_styles(self, doc: OpenDocumentText) -> None:
        """Configure document styles with branding colors."""
        primary = self._branding.primary_color if self._branding else "#1a73e8"

        # Font
        font = FontFace(
            name="Liberation Sans",
            fontfamily="Liberation Sans",
            fontfamilygeneric="swiss",
            fontpitch="variable",
        )
        doc.fontfacedecls.addElement(font)

        mono_font = FontFace(
            name="Liberation Mono",
            fontfamily="Liberation Mono",
            fontfamilygeneric="modern",
            fontpitch="fixed",
        )
        doc.fontfacedecls.addElement(mono_font)

        # Heading styles
        for level, size in [(1, "22pt"), (2, "18pt"), (3, "14pt"), (4, "12pt")]:
            style = Style(name=f"Heading {level}", family="paragraph")
            style.addElement(
                TextProperties(
                    fontsize=size,
                    fontweight="bold",
                    color=primary,
                    fontname="Liberation Sans",
                )
            )
            style.addElement(
                ParagraphProperties(
                    margintop="16pt",
                    marginbottom="8pt",
                    keepwithnext="always",
                )
            )
            doc.styles.addElement(style)

        # Normal text
        normal = Style(name="Normal", family="paragraph")
        normal.addElement(
            TextProperties(fontsize="10pt", fontname="Liberation Sans")
        )
        normal.addElement(ParagraphProperties(marginbottom="6pt"))
        doc.styles.addElement(normal)

        # Code style
        code_style = Style(name="Code", family="paragraph")
        code_style.addElement(
            TextProperties(
                fontsize="9pt",
                fontname="Liberation Mono",
            )
        )
        code_style.addElement(
            ParagraphProperties(
                backgroundcolor="#f5f5f5",
                padding="8pt",
                marginbottom="8pt",
            )
        )
        doc.styles.addElement(code_style)

        # Inline code
        inline_code = Style(name="InlineCode", family="text")
        inline_code.addElement(
            TextProperties(
                fontsize="9pt",
                fontname="Liberation Mono",
                backgroundcolor="#f5f5f5",
            )
        )
        doc.styles.addElement(inline_code)

        # Bold
        bold_style = Style(name="Bold", family="text")
        bold_style.addElement(TextProperties(fontweight="bold"))
        doc.styles.addElement(bold_style)

        # Italic
        italic_style = Style(name="Italic", family="text")
        italic_style.addElement(TextProperties(fontstyle="italic"))
        doc.styles.addElement(italic_style)

        # Link
        link_style = Style(name="Link", family="text")
        link_style.addElement(
            TextProperties(color=primary, textunderlinestyle="solid")
        )
        doc.styles.addElement(link_style)

        # Cover styles
        cover_title = Style(name="CoverTitle", family="paragraph")
        cover_title.addElement(
            TextProperties(fontsize="28pt", fontweight="bold", color=primary)
        )
        cover_title.addElement(
            ParagraphProperties(textalign="center", margintop="40pt", marginbottom="12pt")
        )
        doc.styles.addElement(cover_title)

        cover_meta = Style(name="CoverMeta", family="paragraph")
        cover_meta.addElement(TextProperties(fontsize="10pt", color="#999999"))
        cover_meta.addElement(ParagraphProperties(textalign="center"))
        doc.styles.addElement(cover_meta)

        # Footer style
        footer_style = Style(name="Footer", family="paragraph")
        footer_style.addElement(TextProperties(fontsize="7pt", color="#999999"))
        footer_style.addElement(ParagraphProperties(textalign="center"))
        doc.styles.addElement(footer_style)

        # Table styles
        table_style = Style(name="LeafpressTable", family="table")
        table_style.addElement(TableProperties(width="6.5in", align="margins"))
        doc.automaticstyles.addElement(table_style)

        cell_style = Style(name="TableCell", family="table-cell")
        cell_style.addElement(
            TableCellProperties(
                padding="4pt",
                borderbottom="0.5pt solid #dddddd",
                borderleft="0.5pt solid #dddddd",
                borderright="0.5pt solid #dddddd",
                bordertop="0.5pt solid #dddddd",
            )
        )
        doc.automaticstyles.addElement(cell_style)

        header_cell = Style(name="TableHeaderCell", family="table-cell")
        header_cell.addElement(
            TableCellProperties(
                padding="4pt",
                backgroundcolor="#f5f5f5",
                borderbottom="0.5pt solid #dddddd",
                borderleft="0.5pt solid #dddddd",
                borderright="0.5pt solid #dddddd",
                bordertop="0.5pt solid #dddddd",
            )
        )
        doc.automaticstyles.addElement(header_cell)

    def _setup_page_layout(self, doc: OpenDocumentText) -> None:
        """Configure page layout and footer."""
        layout = PageLayout(name="PageLayout")
        layout.addElement(
            PageLayoutProperties(
                pagewidth="8.5in",
                pageheight="11in",
                margintop="25mm",
                marginbottom="25mm",
                marginleft="20mm",
                marginright="20mm",
            )
        )

        # Footer with branding
        footer_content = Footer()
        footer_parts: list[str] = []
        if self._branding and self._branding.footer.custom_text:
            footer_parts.append(self._branding.footer.custom_text)
        if self._git_info:
            footer_parts.append(self._git_info.format_version_string())
        footer_parts.append("Made with LeafPress")

        footer_para = P(stylename="Footer")
        footer_para.addText(" \u00b7 ".join(footer_parts))
        footer_content.addElement(footer_para)

        doc.automaticstyles.addElement(layout)

        master = MasterPage(name="Standard", pagelayoutname="PageLayout")
        master.addElement(footer_content)
        doc.masterstyles.addElement(master)

    def _add_cover_page(self, doc: OpenDocumentText) -> None:
        """Add a branded cover page."""
        # Logo
        if self._branding and self._branding.logo_path:
            logo_path = self._branding.logo_path
            if not logo_path.startswith(("http://", "https://")) and Path(logo_path).exists():
                self._add_image(doc, Path(logo_path))

        # Company
        if self._branding and self._branding.company_name:
            p = P(stylename="CoverMeta")
            p.addText(self._branding.company_name)
            doc.text.addElement(p)

        # Title
        project = (
            self._branding.project_name if self._branding else self._mkdocs_cfg.site_name
        )
        title_p = P(stylename="CoverTitle")
        title_p.addText(project)
        doc.text.addElement(title_p)

        # Subtitle
        if self._branding and self._branding.subtitle:
            p = P(stylename="CoverMeta")
            p.addText(self._branding.subtitle)
            doc.text.addElement(p)

        # Document owner
        if self._branding and self._branding.document_owner:
            p = P(stylename="CoverMeta")
            p.addText(f"Document Owner: {self._branding.document_owner}")
            doc.text.addElement(p)

        # Review cycle
        if self._branding and self._branding.review_cycle:
            p = P(stylename="CoverMeta")
            p.addText(f"Review Cycle: {self._branding.review_cycle}")
            doc.text.addElement(p)

        # Version
        if self._git_info:
            p = P(stylename="CoverMeta")
            p.addText(self._git_info.format_version_string())
            doc.text.addElement(p)

        # Date
        p = P(stylename="CoverMeta")
        now = datetime.now() if self._local_time else datetime.now(timezone.utc)
        p.addText(now.strftime("%B %d, %Y"))
        doc.text.addElement(p)

        # Spacer
        doc.text.addElement(P())

    def _add_toc(
        self,
        doc: OpenDocumentText,
        html_pages: list[tuple[NavItem, str]],
    ) -> None:
        """Add a simple table of contents."""
        heading = H(outlinelevel=1, stylename="Heading 1")
        heading.addText("Table of Contents")
        doc.text.addElement(heading)

        for item, _html in html_pages:
            if item.path is not None:
                indent = "    " * item.level
                p = P(stylename="Normal")
                p.addText(f"{indent}{item.title}")
                doc.text.addElement(p)
            elif item.children:
                p = P(stylename="Normal")
                bold = Span(stylename="Bold")
                bold.addText(item.title)
                p.addElement(bold)
                doc.text.addElement(p)

        doc.text.addElement(P())

    def _convert_html(self, doc: OpenDocumentText, html: str) -> None:
        """Convert an HTML fragment and append to the ODT document."""
        if not html.strip():
            return

        soup = BeautifulSoup(html, "lxml")
        body = soup.find("body")
        if body is None:
            body = soup

        for element in body.children:
            if isinstance(element, Tag):
                self._process_element(doc, element)

    def _process_element(self, doc: OpenDocumentText, element: Tag) -> None:
        """Dispatch an HTML element to the appropriate handler."""
        tag = element.name
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = min(int(tag[1]), 4)
            heading = H(outlinelevel=level, stylename=f"Heading {level}")
            heading.addText(element.get_text(strip=True))
            doc.text.addElement(heading)
        elif tag == "p":
            p = P(stylename="Normal")
            self._add_inline(p, element)
            doc.text.addElement(p)
        elif tag in ("ul", "ol"):
            self._handle_list(doc, element)
        elif tag == "table":
            self._handle_table(doc, element)
        elif tag == "pre":
            code_text = element.get_text()
            p = P(stylename="Code")
            p.addText(code_text)
            doc.text.addElement(p)
        elif tag == "blockquote":
            p = P(stylename="Normal")
            italic = Span(stylename="Italic")
            italic.addText(element.get_text(strip=True))
            p.addElement(italic)
            doc.text.addElement(p)
        elif tag == "hr":
            p = P(stylename="Normal")
            p.addText("─" * 40)
            doc.text.addElement(p)
        elif tag in ("div", "section", "article", "details"):
            for child in element.children:
                if isinstance(child, Tag):
                    self._process_element(doc, child)

    def _add_inline(self, parent: P, element: Tag) -> None:
        """Add inline formatted content to a paragraph."""
        for child in element.children:
            if isinstance(child, NavigableString):
                text = str(child)
                if text.strip() or text == " ":
                    parent.addText(text)
            elif isinstance(child, Tag):
                if child.name in ("strong", "b"):
                    span = Span(stylename="Bold")
                    span.addText(child.get_text())
                    parent.addElement(span)
                elif child.name in ("em", "i"):
                    span = Span(stylename="Italic")
                    span.addText(child.get_text())
                    parent.addElement(span)
                elif child.name in ("code", "kbd"):
                    span = Span(stylename="InlineCode")
                    span.addText(child.get_text())
                    parent.addElement(span)
                elif child.name == "a":
                    span = Span(stylename="Link")
                    span.addText(child.get_text())
                    parent.addElement(span)
                elif child.name == "br":
                    parent.addText("\n")
                elif child.name == "img" and any(
                    c in child.get("class", []) for c in ("emojione", "twemoji", "gemoji")
                ):
                    alt = child.get("alt", "")
                    if alt:
                        parent.addText(alt)
                else:
                    self._add_inline(parent, child)

    def _handle_list(self, doc: OpenDocumentText, element: Tag) -> None:
        """Convert HTML list to ODT list items as indented paragraphs."""
        for li in element.find_all("li", recursive=False):
            p = P(stylename="Normal")
            prefix = "\u2022 " if element.name == "ul" else ""
            if prefix:
                p.addText(prefix)
            self._add_inline(p, li)
            doc.text.addElement(p)

    def _handle_table(self, doc: OpenDocumentText, element: Tag) -> None:
        """Convert HTML table to ODT table."""
        rows = element.find_all("tr")
        if not rows:
            return

        first_row = rows[0]
        cols = first_row.find_all(["th", "td"])
        if not cols:
            return

        table = Table(stylename="LeafpressTable")

        # Add columns
        col_style = Style(name="TableCol", family="table-column")
        col_style.addElement(TableColumnProperties(columnwidth=f"{6.5 / len(cols):.2f}in"))
        doc.automaticstyles.addElement(col_style)

        for _i in range(len(cols)):
            table.addElement(TableColumn(stylename="TableCol"))

        for row_idx, tr in enumerate(rows):
            table_row = TableRow()
            cells = tr.find_all(["th", "td"])
            for cell in cells:
                is_header = cell.name == "th" or row_idx == 0
                style = "TableHeaderCell" if is_header else "TableCell"
                tc = TableCell(stylename=style)
                p = P(stylename="Normal")
                if is_header:
                    bold = Span(stylename="Bold")
                    bold.addText(cell.get_text(strip=True))
                    p.addElement(bold)
                else:
                    p.addText(cell.get_text(strip=True))
                tc.addElement(p)
                table_row.addElement(tc)
            table.addElement(table_row)

        doc.text.addElement(table)

    def _add_image(self, doc: OpenDocumentText, image_path: Path) -> None:
        """Add an image to the document."""
        p = P(stylename="Normal")
        img_style = Style(name="ImageFrame", family="graphic")
        img_style.addElement(
            GraphicProperties(
                verticalpos="top",
                verticalrel="paragraph",
                horizontalpos="center",
                horizontalrel="paragraph",
            )
        )
        doc.automaticstyles.addElement(img_style)

        frame = Frame(
            stylename="ImageFrame",
            width="4in",
            height="2in",
        )
        href = doc.addPicture(str(image_path))
        frame.addElement(Image(href=href))
        p.addElement(frame)
        doc.text.addElement(p)

    def _add_watermark_style(self, doc: OpenDocumentText) -> None:
        """Add watermark style and insert watermark text on each page via header."""
        if not self._branding or not self._branding.watermark.text:
            return

        wm = self._branding.watermark

        # Create a watermark paragraph style
        wm_style = Style(name="Watermark", family="paragraph")
        wm_style.addElement(
            TextProperties(
                fontsize="48pt",
                fontweight="bold",
                color=wm.color,
                fontstyle="normal",
            )
        )
        wm_style.addElement(
            ParagraphProperties(textalign="center", margintop="200pt")
        )
        doc.styles.addElement(wm_style)

        # Insert watermark text at the very beginning of the document
        wm_para = P(stylename="Watermark")
        wm_para.addText(wm.text)
        # Prepend to document body
        if doc.text.childNodes:
            doc.text.insertBefore(wm_para, doc.text.childNodes[0])
        else:
            doc.text.addElement(wm_para)
