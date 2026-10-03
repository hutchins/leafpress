"""PDF generation via WeasyPrint."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from jinja2 import Environment, PackageLoader
from markupsafe import Markup
from weasyprint import CSS, HTML

from leafpress.asset_policy import AssetPolicy
from leafpress.base_renderer import build_asset_policy, replace_checkboxes, resolve_logo_uri
from leafpress.config import BrandingConfig
from leafpress.exceptions import RenderError
from leafpress.git_info import GitVersion
from leafpress.mkdocs_parser import MkDocsConfig, NavItem
from leafpress.pdf.styles import generate_pdf_css
from leafpress.render_errors import format_render_error

logger = logging.getLogger(__name__)


class PdfRenderer:
    """Generates a single PDF from a sequence of HTML pages."""

    def __init__(
        self,
        branding: BrandingConfig | None,
        git_info: GitVersion | None,
        mkdocs_cfg: MkDocsConfig,
        asset_policy: AssetPolicy | None = None,
    ) -> None:
        self._branding = branding
        self._git_info = git_info
        self._mkdocs_cfg = mkdocs_cfg
        self._asset_policy = asset_policy or build_asset_policy(mkdocs_cfg, branding)
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
        now = datetime.now() if local_time else datetime.now(UTC)

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
                    # Rendered page HTML (sanitized for untrusted sources)
                    content=Markup(html_content),  # noqa: S704
                    is_section_header=(item.path is None),
                )
            )

        # Generate CSS
        css_string = generate_pdf_css(self._branding, self._git_info, local_time=local_time)

        # Post-process: replace checkbox inputs with unicode for print
        combined = "\n".join(sections_html)
        combined = replace_checkboxes(combined)

        # Render with WeasyPrint. The restricted fetcher keeps document content
        # from pulling in local files outside the project or internal URLs.
        from leafpress.pdf.url_fetcher import RestrictedURLFetcher

        full_html = self._wrap_document(combined)
        fetcher = RestrictedURLFetcher(self._asset_policy)
        html_doc = HTML(
            string=full_html,
            base_url=str(self._mkdocs_cfg.docs_dir),
            url_fetcher=fetcher,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            html_doc.write_pdf(
                str(output_path),
                stylesheets=[CSS(string=css_string, url_fetcher=fetcher)],
            )
        except Exception as exc:
            raise RenderError(format_render_error("PDF", exc)) from exc

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
