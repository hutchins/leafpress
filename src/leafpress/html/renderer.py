"""Static HTML generation from converted MkDocs pages."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, PackageLoader
from markupsafe import Markup, escape

from leafpress.asset_policy import AssetPolicy
from leafpress.base_renderer import (
    build_asset_policy,
    image_data_uri,
    make_anchor_id,
    replace_checkboxes,
    rewrite_local_images,
)
from leafpress.config import BrandingConfig
from leafpress.document_meta import FOOTER_SEPARATOR, CoverFields, footer_parts, render_time
from leafpress.git_info import GitVersion
from leafpress.logo import load_logo
from leafpress.mkdocs_parser import MkDocsConfig, NavItem


class HtmlRenderer:
    """Generates a single self-contained HTML file from a sequence of HTML pages."""

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
        now = render_time(local_time)

        # Build cover HTML
        cover_html = ""
        if cover_page:
            cover_tmpl = self._jinja.get_template("cover.html.j2")
            cover = CoverFields.build(self._branding, self._mkdocs_cfg.site_name, now)
            logo = load_logo(self._branding)
            cover_html = cover_tmpl.render(
                **cover.template_context(),
                logo_path=logo.data_uri() if logo else "",
                git_info=self._git_info,
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
                    # Rendered page HTML (sanitized for untrusted sources)
                    content=Markup(html_content),  # noqa: S704
                    is_section_header=(item.path is None),
                    page_id=make_anchor_id(item.title),
                )
            )

        # Build footer. Markup.join escapes each part: custom_text comes from
        # leafpress.yml (possibly an untrusted repo's) and the branch name from git
        footer_text = escape(FOOTER_SEPARATOR).join(
            footer_parts(self._branding, self._git_info, now)
        )

        # Build watermark HTML
        watermark_html = ""
        if self._branding and self._branding.watermark.text:
            watermark_html = (
                f'<div class="lp-watermark">{escape(self._branding.watermark.text)}</div>'
            )

        # Render full document
        doc_tmpl = self._jinja.get_template("document.html.j2")
        site_name = self._branding.project_name if self._branding else self._mkdocs_cfg.site_name
        # Each piece below is already-escaped output of an autoescaping Jinja
        # template, generated CSS, or explicitly escaped/Markup-joined text.
        full_html = doc_tmpl.render(
            site_name=site_name,
            css=Markup(css),  # noqa: S704
            cover=Markup(cover_html),  # noqa: S704
            toc=Markup(toc_html),  # noqa: S704
            sections=Markup("\n".join(sections)),  # noqa: S704
            footer_text=footer_text,
            nav_items=html_pages,
            watermark=Markup(watermark_html),  # noqa: S704
        )

        # Post-process checkboxes
        full_html = replace_checkboxes(full_html)
        # Embed local images (content, mermaid) so the file is portable; the logo
        # is already a data: URI
        full_html = rewrite_local_images(full_html, self._asset_policy, image_data_uri)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(full_html, encoding="utf-8")
