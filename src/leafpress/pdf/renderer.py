"""PDF generation via WeasyPrint."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, PackageLoader
from markupsafe import Markup
from weasyprint import CSS, HTML

from leafpress.base_renderer import replace_checkboxes, resolve_logo_uri
from leafpress.config import BrandingConfig
from leafpress.exceptions import RenderError
from leafpress.git_info import GitVersion
from leafpress.mkdocs_parser import MkDocsConfig, NavItem
from leafpress.pdf.styles import generate_pdf_css

logger = logging.getLogger(__name__)


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
                    logo_path=resolve_logo_uri(self._branding),
                    git_info=self._git_info,
                    author=self._branding.author if self._branding else "",
                    author_email=self._branding.author_email if self._branding else "",
                    document_owner=self._branding.document_owner if self._branding else "",
                    review_cycle=self._branding.review_cycle if self._branding else "",
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
        css_string = generate_pdf_css(self._branding, self._git_info, local_time=local_time)

        # Post-process: replace checkbox inputs with unicode for print
        combined = "\n".join(sections_html)
        combined = replace_checkboxes(combined)

        # Render with WeasyPrint
        full_html = self._wrap_document(combined)
        html_doc = HTML(
            string=full_html,
            base_url=str(self._mkdocs_cfg.docs_dir),
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            html_doc.write_pdf(
                str(output_path),
                stylesheets=[CSS(string=css_string)],
            )
        except Exception as exc:
            raise RenderError(self._format_pdf_error(exc)) from exc

    def _wrap_document(self, body: str) -> str:
        """Wrap body content in a full HTML5 document."""
        watermark_div = ""
        if self._branding and self._branding.watermark.text:
            from markupsafe import escape

            watermark_div = f'<div class="watermark">{escape(self._branding.watermark.text)}</div>'
        return (
            '<!DOCTYPE html>\n<html>\n<head><meta charset="utf-8"></head>\n'
            f"<body>\n{watermark_div}\n{body}\n</body>\n</html>"
        )

    @staticmethod
    def _format_pdf_error(exc: Exception) -> str:
        """Produce a user-friendly error message for PDF rendering failures."""
        exc_name = type(exc).__name__
        exc_msg = str(exc)

        if "UnrecognizedImageError" in exc_name or "unrecognized image" in exc_msg.lower():
            return (
                f"PDF rendering failed due to an unrecognized image format.\n"
                f"  This often happens when an SVG image is used but the required\n"
                f"  system libraries (librsvg / libcairo) are not installed.\n"
                f"  Run 'leafpress doctor' to check your environment.\n"
                f"  Tip: Convert SVG images to PNG, or install librsvg:\n"
                f"    macOS:  brew install librsvg\n"
                f"    Ubuntu: sudo apt install librsvg2-dev\n"
                f"  Original error: {exc_name}: {exc_msg}"
            )

        if "image" in exc_msg.lower() or "image" in exc_name.lower():
            return (
                f"PDF rendering failed due to an image error.\n"
                f"  Check that all images referenced in your docs exist and are in\n"
                f"  a supported format (PNG, JPEG, GIF, or SVG with librsvg).\n"
                f"  Run 'leafpress doctor' to check your environment.\n"
                f"  Original error: {exc_name}: {exc_msg}"
            )

        return (
            f"PDF rendering failed: {exc_name}: {exc_msg}\n"
            f"  Run 'leafpress doctor' to check your environment.\n"
            f"  If this persists, please report it at https://github.com/leafpress/leafpress/issues"
        )
