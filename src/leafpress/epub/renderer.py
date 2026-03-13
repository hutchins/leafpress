"""EPUB generation from converted MkDocs pages."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ebooklib import epub
from jinja2 import Environment, PackageLoader

from leafpress.config import BrandingConfig
from leafpress.git_info import GitVersion
from leafpress.mkdocs_parser import MkDocsConfig, NavItem


class EpubRenderer:
    """Generates an EPUB file from a sequence of HTML pages."""

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
        now = datetime.now() if local_time else datetime.now(timezone.utc)

        # Cover page chapter
        if cover_page:
            cover_tmpl = self._jinja.get_template("cover.html.j2")
            cover_html = cover_tmpl.render(
                company_name=(self._branding.company_name if self._branding else ""),
                project_name=site_name,
                subtitle=self._branding.subtitle if self._branding else "",
                logo_path="",  # skip logo in EPUB (no embedded data URI needed)
                git_info=self._git_info,
                author=self._branding.author if self._branding else "",
                author_email=self._branding.author_email if self._branding else "",
                document_owner=self._branding.document_owner if self._branding else "",
                review_cycle=self._branding.review_cycle if self._branding else "",
                date=now.strftime("%B %d, %Y"),
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
            from markupsafe import escape

            watermark_html = (
                f'<div class="lp-watermark">{escape(self._branding.watermark.text)}</div>'
            )

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
            page_id = self._make_id(item.title)

            chapter = epub.EpubHtml(
                title=item.title,
                file_name=file_name,
                lang="en",
            )

            # Build chapter body
            body = f'<h1 id="{page_id}">{item.title}</h1>\n'
            if watermark_html:
                body += watermark_html + "\n"
            body += self._replace_checkboxes(html_content)

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

        # Footer chapter
        footer_parts: list[str] = []
        if self._branding and self._branding.footer.custom_text:
            footer_parts.append(self._branding.footer.custom_text)
        if self._git_info:
            footer_parts.append(self._git_info.format_version_string())
        if self._branding is None or self._branding.footer.include_render_date:
            footer_parts.append(f"Generated {now.strftime('%Y-%m-%d')}")
        footer_parts.append("Made with LeafPress")
        footer_text = " &middot; ".join(footer_parts)

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

    @staticmethod
    def _make_id(title: str) -> str:
        """Convert a title to a URL-safe anchor ID."""
        slug = re.sub(r"[^\w\s-]", "", title.lower())
        return re.sub(r"[\s]+", "-", slug).strip("-")

    @staticmethod
    def _replace_checkboxes(html: str) -> str:
        """Replace <input type='checkbox'> with unicode symbols."""
        html = re.sub(
            r'<label class="task-list-control">'
            r'<input type="checkbox" disabled checked/>'
            r'<span class="task-list-indicator"></span>'
            r"</label>\s*",
            '<span class="task-checkbox checked">&#x2611;</span> ',
            html,
        )
        html = re.sub(
            r'<label class="task-list-control">'
            r'<input type="checkbox" disabled/>'
            r'<span class="task-list-indicator"></span>'
            r"</label>\s*",
            '<span class="task-checkbox">&#x2610;</span> ',
            html,
        )
        return html
