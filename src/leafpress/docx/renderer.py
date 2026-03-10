"""DOCX generation using python-docx."""

from __future__ import annotations

import io
from datetime import datetime, timezone
from pathlib import Path

import requests
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

from leafpress.config import BrandingConfig
from leafpress.docx.html_converter import HtmlToDocxConverter
from leafpress.docx.styles import apply_branding_styles
from leafpress.git_info import GitVersion
from leafpress.mkdocs_parser import MkDocsConfig, NavItem


class DocxRenderer:
    """Generates a single DOCX file from HTML pages."""

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
    ) -> None:
        """Build a DOCX document from converted HTML pages."""
        template_path = None
        if self._branding and self._branding.docx.template_path:
            template_path = self._branding.docx.template_path

        doc = Document(str(template_path)) if template_path else Document()

        apply_branding_styles(doc, self._branding)
        self._setup_header(doc)
        self._setup_footer(doc)

        if cover_page:
            self._add_cover_page(doc)

        if include_toc:
            self._add_toc_placeholder(doc)

        converter = HtmlToDocxConverter(doc, self._mkdocs_cfg.docs_dir)
        first_content = True
        for item, html_content in html_pages:
            if item.path is None:
                # Section header
                if not first_content:
                    doc.add_page_break()
                doc.add_heading(item.title, level=min(item.level + 1, 4))
                first_content = False
                continue

            if not first_content:
                doc.add_page_break()
            converter.convert(html_content)
            first_content = False

        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(output_path))

    def _setup_header(self, doc: Document) -> None:
        """Add company name and logo to document header."""
        section = doc.sections[0]
        header = section.header
        header.is_linked_to_previous = False

        paragraph = header.paragraphs[0]
        paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT

        logo_stream = self._get_logo_stream()
        if logo_stream:
            run = paragraph.add_run()
            run.add_picture(logo_stream, width=Inches(0.5))
            paragraph.add_run("  ")

        if self._branding:
            run = paragraph.add_run(self._branding.company_name)
            run.font.size = Pt(8)
            run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)

    def _setup_footer(self, doc: Document) -> None:
        """Add version info to document footer."""
        section = doc.sections[0]
        footer = section.footer
        footer.is_linked_to_previous = False

        paragraph = footer.paragraphs[0]
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER

        footer_parts: list[str] = []
        if self._branding and self._branding.footer.custom_text:
            footer_parts.append(self._branding.footer.custom_text)
        if self._branding and self._branding.footer.repo_url:
            footer_parts.append(self._branding.footer.repo_url)
        if self._git_info:
            version_parts: list[str] = []
            gi = self._git_info
            footer = self._branding.footer if self._branding else None
            if (footer is None or footer.include_tag) and gi.tag:
                dist = gi.tag_distance
                version_parts.append(f"{gi.tag}+{dist}" if dist and dist > 0 else gi.tag)
            if footer is None or footer.include_commit:
                version_parts.append(gi.commit_hash)
            if footer is None or footer.include_date:
                version_parts.append(gi.commit_date.strftime("%Y-%m-%d"))
            if footer and footer.include_branch:
                version_parts.append(gi.branch)
            if version_parts:
                footer_parts.append(" | ".join(version_parts))

        footer_parts.append("Made with LeafPress · leafpress.dev")
        run = paragraph.add_run(" - ".join(footer_parts))
        run.font.size = Pt(7)
        run.font.color.rgb = RGBColor(0x99, 0x99, 0x99)

    def _add_cover_page(self, doc: Document) -> None:
        """Add a branded cover page."""
        # Add some vertical spacing
        for _ in range(6):
            doc.add_paragraph()

        # Logo
        logo_stream = self._get_logo_stream()
        if logo_stream:
            para = doc.add_paragraph()
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = para.add_run()
            run.add_picture(logo_stream, width=Inches(2.0))

        # Company name
        if self._branding:
            para = doc.add_paragraph()
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = para.add_run(self._branding.company_name)
            run.font.size = Pt(14)
            run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)

        # Project name
        project_name = self._branding.project_name if self._branding else self._mkdocs_cfg.site_name
        para = doc.add_paragraph()
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = para.add_run(project_name)
        run.font.size = Pt(28)
        run.bold = True

        # Subtitle
        if self._branding and self._branding.subtitle:
            para = doc.add_paragraph()
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = para.add_run(self._branding.subtitle)
            run.font.size = Pt(16)
            run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)

        # Author (and optional email on same line)
        if self._branding and (self._branding.author or self._branding.author_email):
            para = doc.add_paragraph()
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            if self._branding.author:
                run = para.add_run(self._branding.author)
                run.font.size = Pt(12)
                run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
            if self._branding.author_email:
                prefix = " <" if self._branding.author else ""
                suffix = ">" if self._branding.author else ""
                run = para.add_run(f"{prefix}{self._branding.author_email}{suffix}")
                run.font.size = Pt(10)
                run.font.color.rgb = RGBColor(0x99, 0x99, 0x99)

        # Version and date
        for _ in range(4):
            doc.add_paragraph()

        if self._git_info:
            para = doc.add_paragraph()
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = para.add_run(self._git_info.format_version_string())
            run.font.size = Pt(10)
            run.font.color.rgb = RGBColor(0x99, 0x99, 0x99)

        para = doc.add_paragraph()
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = para.add_run(datetime.now(timezone.utc).strftime("%B %d, %Y"))
        run.font.size = Pt(10)
        run.font.color.rgb = RGBColor(0x99, 0x99, 0x99)

        doc.add_page_break()

    def _get_logo_stream(self) -> io.BytesIO | None:
        """Return logo image bytes as a stream, fetching from URL if needed."""
        if not self._branding or not self._branding.logo_path:
            return None
        logo = self._branding.logo_path
        if logo.startswith(("http://", "https://")):
            response = requests.get(logo, timeout=30)
            response.raise_for_status()
            return io.BytesIO(response.content)
        path = Path(logo)
        if path.exists():
            return io.BytesIO(path.read_bytes())
        return None

    def _add_toc_placeholder(self, doc: Document) -> None:
        """Insert a Word TOC field code.

        The actual TOC is generated when the user opens the doc in Word
        and presses 'Update Fields' (Ctrl+A, F9).
        """
        doc.add_heading("Table of Contents", level=1)

        paragraph = doc.add_paragraph()
        run = paragraph.add_run()
        fld_char = OxmlElement("w:fldChar")
        fld_char.set(qn("w:fldCharType"), "begin")
        run._element.append(fld_char)

        run = paragraph.add_run()
        instr_text = OxmlElement("w:instrText")
        instr_text.set(qn("xml:space"), "preserve")
        instr_text.text = ' TOC \\o "1-3" \\h \\z \\u '
        run._element.append(instr_text)

        run = paragraph.add_run()
        fld_char = OxmlElement("w:fldChar")
        fld_char.set(qn("w:fldCharType"), "separate")
        run._element.append(fld_char)

        run = paragraph.add_run("Right-click and select 'Update Field' to generate TOC")
        run.font.color.rgb = RGBColor(0x99, 0x99, 0x99)

        run = paragraph.add_run()
        fld_char = OxmlElement("w:fldChar")
        fld_char.set(qn("w:fldCharType"), "end")
        run._element.append(fld_char)

        doc.add_page_break()
