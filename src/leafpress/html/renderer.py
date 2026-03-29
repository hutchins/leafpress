"""Static HTML generation from converted MkDocs pages."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, PackageLoader
from markupsafe import Markup

from leafpress.base_renderer import make_anchor_id, replace_checkboxes, resolve_logo_uri
from leafpress.config import BrandingConfig
from leafpress.git_info import GitVersion
from leafpress.mkdocs_parser import MkDocsConfig, NavItem


class HtmlRenderer:
    """Generates a single self-contained HTML file from a sequence of HTML pages."""

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
            loader=PackageLoader("leafpress.html", "templates"),
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
        """Compose all pages into a single self-contained HTML document."""
        from leafpress.html.styles import generate_html_css

        css = generate_html_css(self._branding)
        now = datetime.now() if local_time else datetime.now(timezone.utc)

        # Build cover HTML
        cover_html = ""
        if cover_page:
            cover_tmpl = self._jinja.get_template("cover.html.j2")
            cover_html = cover_tmpl.render(
                company_name=(self._branding.company_name if self._branding else ""),
                project_name=(
                    self._branding.project_name if self._branding else self._mkdocs_cfg.site_name
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

        # Build TOC HTML
        toc_html = ""
        if include_toc:
            toc_tmpl = self._jinja.get_template("toc.html.j2")
            toc_html = toc_tmpl.render(pages=html_pages)

        # Build content sections
        sections: list[str] = []
        page_tmpl = self._jinja.get_template("page.html.j2")
        for item, html_content in html_pages:
            sections.append(
                page_tmpl.render(
                    title=item.title,
                    level=item.level,
                    content=Markup(html_content),
                    is_section_header=(item.path is None),
                    page_id=make_anchor_id(item.title),
                )
            )

        # Build footer
        footer_parts: list[str] = []
        if self._branding and self._branding.footer.custom_text:
            footer_parts.append(self._branding.footer.custom_text)
        if self._git_info:
            footer_parts.append(self._git_info.format_version_string())
        if self._branding is None or self._branding.footer.include_render_date:
            footer_parts.append(f"Generated {now.strftime('%Y-%m-%d')}")
        footer_parts.append("Made with LeafPress")
        footer_text = " &middot; ".join(footer_parts)

        # Build watermark HTML
        watermark_html = ""
        if self._branding and self._branding.watermark.text:
            from markupsafe import escape

            watermark_html = (
                f'<div class="lp-watermark">{escape(self._branding.watermark.text)}</div>'
            )

        # Render full document
        doc_tmpl = self._jinja.get_template("document.html.j2")
        site_name = self._branding.project_name if self._branding else self._mkdocs_cfg.site_name
        full_html = doc_tmpl.render(
            site_name=site_name,
            css=Markup(css),
            cover=Markup(cover_html),
            toc=Markup(toc_html),
            sections=Markup("\n".join(sections)),
            footer_text=Markup(footer_text),
            nav_items=html_pages,
            watermark=Markup(watermark_html),
        )

        # Post-process checkboxes
        full_html = replace_checkboxes(full_html)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(full_html, encoding="utf-8")
