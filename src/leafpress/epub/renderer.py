"""EPUB generation from converted MkDocs pages."""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from ebooklib import epub
from jinja2 import Environment, PackageLoader
from markupsafe import escape

from leafpress.asset_policy import AssetPolicy
from leafpress.base_renderer import (
    build_asset_policy,
    image_mime_type,
    make_anchor_id,
    replace_checkboxes,
    rewrite_local_images,
)
from leafpress.config import BrandingConfig
from leafpress.document_meta import FOOTER_SEPARATOR, CoverFields, footer_parts, render_time
from leafpress.git_info import GitVersion
from leafpress.logo import load_logo
from leafpress.mkdocs_parser import MkDocsConfig, NavItem


class EpubRenderer:
    """Generates an EPUB file from a sequence of HTML pages."""

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
        """Compose all pages into an EPUB document."""
        from leafpress.epub.styles import generate_epub_css

        book = epub.EpubBook()

        # Metadata
        site_name = self._branding.project_name if self._branding else self._mkdocs_cfg.site_name
        book.set_identifier(str(uuid.uuid4()))
        book.set_title(site_name)
        book.set_language("en")

        if self._branding and self._branding.author:
            book.add_author(self._branding.author)
        if self._branding and self._branding.copyright_text:
            book.add_metadata("DC", "rights", self._branding.copyright_text)

        # CSS stylesheet
        css_content = generate_epub_css(self._branding)
        css_item = epub.EpubItem(
            uid="style_leafpress",
            file_name="style/leafpress.css",
            media_type="text/css",
            content=css_content,
        )
        book.add_item(css_item)

        spine: list[str | epub.EpubHtml] = ["nav"]
        toc_items: list[epub.Link | tuple[epub.Section, list]] = []
        now = render_time(local_time)

        # Cover page chapter
        if cover_page:
            cover_tmpl = self._jinja.get_template("cover.html.j2")
            cover = CoverFields.build(self._branding, self._mkdocs_cfg.site_name, now)
            # The logo is packaged in the EPUB; cover.xhtml sits at the root
            logo = load_logo(self._branding)
            logo_src = ""
            if logo is not None:
                logo_src = f"images/logo{logo.extension}"
                book.add_item(
                    epub.EpubItem(
                        uid="img_logo",
                        file_name=logo_src,
                        media_type=logo.mime_type,
                        content=logo.data,
                    )
                )
            cover_html = cover_tmpl.render(
                **cover.template_context(),
                logo_path=logo_src,
                git_info=self._git_info,
            )
            cover_chapter = epub.EpubHtml(
                title="Cover",
                file_name="cover.xhtml",
                lang="en",
            )
            cover_chapter.content = self._wrap_html(cover_html, css_item)
            cover_chapter.add_link(href="style/leafpress.css", rel="stylesheet", type="text/css")
            book.add_item(cover_chapter)
            spine.append(cover_chapter)

        # Watermark text (inline in each chapter if configured)
        watermark_html = ""
        if self._branding and self._branding.watermark.text:
            watermark_html = (
                f'<div class="lp-watermark">{escape(self._branding.watermark.text)}</div>'
            )

        # Local images are packaged inside the EPUB (file:// links don't work
        # in e-readers). Content-addressed names dedupe repeated images.
        added_images: dict[Path, str] = {}

        def add_image(path: Path) -> str:
            if path not in added_images:
                data = path.read_bytes()
                name = f"images/{hashlib.sha256(data).hexdigest()[:16]}{path.suffix.lower()}"
                if name not in added_images.values():
                    book.add_item(
                        epub.EpubItem(
                            uid=f"img_{len(added_images)}",
                            file_name=name,
                            media_type=image_mime_type(path),
                            content=data,
                        )
                    )
                added_images[path] = name
            return added_images[path]

        # Content chapters
        chapter_idx = 0
        current_section_items: list[epub.EpubHtml] = []
        current_section_name: str | None = None

        for item, html_content in html_pages:
            if item.path is None:
                # Flush previous section
                if current_section_name and current_section_items:
                    toc_items.append((epub.Section(current_section_name), current_section_items))
                current_section_name = item.title
                current_section_items = []
                continue

            chapter_idx += 1
            file_name = f"chapter_{chapter_idx:03d}.xhtml"
            page_id = make_anchor_id(item.title)

            chapter = epub.EpubHtml(
                title=item.title,
                file_name=file_name,
                lang="en",
            )

            # Build chapter body
            body = f'<h1 id="{page_id}">{escape(item.title)}</h1>\n'
            if watermark_html:
                body += watermark_html + "\n"
            body += rewrite_local_images(
                replace_checkboxes(html_content), self._asset_policy, add_image
            )

            chapter.content = self._wrap_html(body, css_item)
            chapter.add_link(href="style/leafpress.css", rel="stylesheet", type="text/css")
            book.add_item(chapter)
            spine.append(chapter)
            current_section_items.append(chapter)

        # Flush last section
        if current_section_name and current_section_items:
            toc_items.append((epub.Section(current_section_name), current_section_items))
        elif current_section_items:
            # Pages without sections — add as direct links
            for ch in current_section_items:
                toc_items.append(epub.Link(ch.file_name, ch.title, ch.file_name.replace(".", "_")))

        # Footer chapter. Markup.join escapes each part: custom_text comes from
        # leafpress.yml (possibly an untrusted repo's) and the branch name from git
        footer_text = escape(FOOTER_SEPARATOR).join(
            footer_parts(self._branding, self._git_info, now)
        )

        footer_chapter = epub.EpubHtml(
            title="About this document",
            file_name="footer.xhtml",
            lang="en",
        )
        footer_chapter.content = self._wrap_html(
            f'<footer class="lp-footer">{footer_text}</footer>', css_item
        )
        footer_chapter.add_link(href="style/leafpress.css", rel="stylesheet", type="text/css")
        book.add_item(footer_chapter)
        spine.append(footer_chapter)

        # Set TOC, navigation, and spine
        book.toc = toc_items
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = spine

        # Write EPUB
        output_path.parent.mkdir(parents=True, exist_ok=True)
        epub.write_epub(str(output_path), book, {})

    @staticmethod
    def _wrap_html(body: str, css_item: epub.EpubItem) -> str:
        """Wrap body content in a minimal XHTML document.

        Note: No XML declaration or DOCTYPE — ebooklib's get_body_content()
        returns empty bytes when those are present.
        """
        return (
            '<html xmlns="http://www.w3.org/1999/xhtml" lang="en">\n'
            "<head>\n"
            '  <meta charset="utf-8" />\n'
            f'  <link rel="stylesheet" href="{css_item.file_name}" type="text/css" />\n'
            "</head>\n"
            f"<body>\n{body}\n</body>\n"
            "</html>"
        )
