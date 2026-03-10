"""PDF generation via WeasyPrint."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, PackageLoader
from markupsafe import Markup
from weasyprint import CSS, HTML

from leafpress.config import BrandingConfig
from leafpress.git_info import GitVersion
from leafpress.mkdocs_parser import MkDocsConfig, NavItem
from leafpress.pdf.styles import generate_pdf_css


class PdfRenderer:
    """Generates a single PDF from a sequence of HTML pages."""

    def __init__(
        self,
        branding: BrandingConfig | None,
        git_info: GitVersion | None,
        mkdocs_cfg: MkDocsConfig,
    ) -> None:
        self._branding = branding
        self._git_info = git_info
        self._mkdocs_cfg = mkdocs_cfg
        self._jinja = Environment(
            loader=PackageLoader("leafpress.pdf", "templates"),
            autoescape=True,
        )

    def render(
        self,
        html_pages: list[tuple[NavItem, str]],
        output_path: Path,
        cover_page: bool = True,
        include_toc: bool = True,
        local_time: bool = False,
    ) -> None:
        """Compose all pages into a single HTML document and render to PDF."""
        sections_html: list[str] = []
        now = datetime.now() if local_time else datetime.now(timezone.utc)

        if cover_page:
            cover_tmpl = self._jinja.get_template("cover.html.j2")
            sections_html.append(
                cover_tmpl.render(
                    company_name=(self._branding.company_name if self._branding else ""),
                    project_name=(
                        self._branding.project_name
                        if self._branding
                        else self._mkdocs_cfg.site_name
                    ),
                    subtitle=self._branding.subtitle if self._branding else "",
                    logo_path=self._resolve_logo_uri(),
                    git_info=self._git_info,
                    author=self._branding.author if self._branding else "",
                    author_email=self._branding.author_email if self._branding else "",
                    date=now.strftime("%B %d, %Y"),
                )
            )

        if include_toc:
            toc_tmpl = self._jinja.get_template("toc.html.j2")
            sections_html.append(toc_tmpl.render(pages=html_pages))

        page_tmpl = self._jinja.get_template("page.html.j2")
        for item, html_content in html_pages:
            sections_html.append(
                page_tmpl.render(
                    title=item.title,
                    level=item.level,
                    content=Markup(html_content),
                    is_section_header=(item.path is None),
                )
            )

        # Generate CSS
        css_string = generate_pdf_css(self._branding, self._git_info)

        # Post-process: replace checkbox inputs with unicode for print
        combined = "\n".join(sections_html)
        combined = self._replace_checkboxes(combined)

        # Render with WeasyPrint
        full_html = self._wrap_document(combined)
        html_doc = HTML(
            string=full_html,
            base_url=str(self._mkdocs_cfg.docs_dir),
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        html_doc.write_pdf(
            str(output_path),
            stylesheets=[CSS(string=css_string)],
        )

    def _wrap_document(self, body: str) -> str:
        """Wrap body content in a full HTML5 document."""
        watermark_div = ""
        if self._branding and self._branding.watermark.text:
            from markupsafe import escape

            watermark_div = (
                f'<div class="watermark">{escape(self._branding.watermark.text)}</div>'
            )
        return (
            '<!DOCTYPE html>\n<html>\n<head><meta charset="utf-8"></head>\n'
            f"<body>\n{watermark_div}\n{body}\n</body>\n</html>"
        )

    @staticmethod
    def _replace_checkboxes(html: str) -> str:
        """Replace <input type="checkbox"> elements with unicode symbols.

        WeasyPrint doesn't render HTML form inputs, so we swap them for
        print-friendly unicode check/uncheck symbols.
        """
        # Checked: ☑  (replaces <input type="checkbox" disabled checked/>)
        html = re.sub(
            r'<label class="task-list-control">'
            r'<input type="checkbox" disabled checked/>'
            r'<span class="task-list-indicator"></span>'
            r"</label>\s*",
            '<span class="task-checkbox task-checkbox-checked">\u2611</span> ',
            html,
        )
        # Unchecked: ☐  (replaces <input type="checkbox" disabled/>)
        html = re.sub(
            r'<label class="task-list-control">'
            r'<input type="checkbox" disabled/>'
            r'<span class="task-list-indicator"></span>'
            r"</label>\s*",
            '<span class="task-checkbox task-checkbox-unchecked">\u2610</span> ',
            html,
        )
        return html

    def _resolve_logo_uri(self) -> str:
        """Get a URI for the logo (http(s):// or file://), or empty string."""
        if self._branding and self._branding.logo_path:
            logo = self._branding.logo_path
            if logo.startswith(("http://", "https://")):
                return logo
            return Path(logo).resolve().as_uri()
        return ""
