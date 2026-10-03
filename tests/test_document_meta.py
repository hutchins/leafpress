"""Shared footer/cover metadata and the shared logo loader, across every format."""

from __future__ import annotations

import gzip
import io
import logging
import re
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from requests.structures import CaseInsensitiveDict

from leafpress.config import BrandingConfig, FooterConfig
from leafpress.document_meta import CREDIT, FOOTER_SEPARATOR, CoverFields, footer_parts
from leafpress.downloads import DownloadError
from leafpress.git_info import GitVersion
from leafpress.logo import MAX_LOGO_BYTES, SVG_MIME, load_logo
from leafpress.mkdocs_parser import MkDocsConfig, NavItem
from tests.helpers import make_png

PNG = make_png()
SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 100"><rect/></svg>'
NOW = datetime(2026, 10, 3, tzinfo=UTC)
GIT = GitVersion(
    commit_hash="abc1234",
    commit_hash_full="abc1234" * 5,
    commit_date=datetime(2026, 9, 1, tzinfo=UTC),
    branch="feature/x",
    tag="v1.2.0",
    is_dirty=False,
    tag_distance=3,
)


def _branding(**footer: object) -> BrandingConfig:
    return BrandingConfig(company_name="Acme", project_name="Docs", footer=FooterConfig(**footer))


# ---------------------------------------------------------------------------
# footer_parts
# ---------------------------------------------------------------------------


class TestFooterParts:
    def test_defaults_without_branding(self) -> None:
        assert footer_parts(None, GIT, NOW) == [
            "v1.2.0+3 | abc1234 | 2026-09-01",
            "Generated 2026-10-03",
            CREDIT,
        ]

    def test_all_fields_in_order(self) -> None:
        branding = _branding(
            custom_text="Confidential",
            repo_url="https://github.com/org/repo",
            include_branch=True,
            include_render_date=True,
        )
        assert footer_parts(branding, GIT, NOW) == [
            "Confidential",
            "https://github.com/org/repo",
            "v1.2.0+3 | abc1234 | 2026-09-01 | feature/x",
            "Generated 2026-10-03",
            CREDIT,
        ]

    def test_version_fields_can_all_be_disabled(self) -> None:
        branding = _branding(
            include_tag=False, include_commit=False, include_date=False, include_render_date=False
        )
        assert footer_parts(branding, GIT, NOW) == [CREDIT]

    def test_tag_without_distance_and_no_git(self) -> None:
        from dataclasses import replace

        on_tag = replace(GIT, tag_distance=0)
        assert footer_parts(_branding(include_render_date=False), on_tag, NOW)[0].startswith(
            "v1.2.0 | "
        )
        assert footer_parts(_branding(include_render_date=False), None, NOW) == [CREDIT]


class TestCoverFields:
    def test_falls_back_to_site_name_without_branding(self) -> None:
        cover = CoverFields.build(None, "Site", NOW)
        assert cover.project_name == "Site" and cover.company_name == ""
        assert cover.date == "October 03, 2026"

    def test_branding_values(self) -> None:
        branding = BrandingConfig(
            company_name="Acme", project_name="Docs", subtitle="Sub", author="Ann"
        )
        ctx = CoverFields.build(branding, "Site", NOW).template_context()
        assert ctx["project_name"] == "Docs" and ctx["subtitle"] == "Sub"
        assert ctx["author"] == "Ann" and ctx["author_email"] == ""


# ---------------------------------------------------------------------------
# The same footer in every format
# ---------------------------------------------------------------------------

FOOTER_BRANDING = dict(
    custom_text="Confidential <b>&",
    repo_url="https://github.com/org/repo",
    include_commit=False,
    include_branch=True,
    include_render_date=False,
)
EXPECTED_FOOTER = FOOTER_SEPARATOR.join(
    [
        "Confidential <b>&",
        "https://github.com/org/repo",
        "v1.2.0+3 | 2026-09-01 | feature/x",
        CREDIT,
    ]
)


@pytest.fixture
def project(tmp_path: Path) -> tuple[BrandingConfig, MkDocsConfig, list[tuple[NavItem, str]]]:
    docs = tmp_path / "docs"
    docs.mkdir()
    cfg = MkDocsConfig("Site", docs, [], [], None, [], tmp_path / "mkdocs.yml")
    branding = _branding(**FOOTER_BRANDING)
    pages = [(NavItem(title="Intro", path="index.md", level=0), "<p>Hello</p>")]
    return branding, cfg, pages


def _unescape(text: str) -> str:
    import html

    return html.unescape(re.sub(r"<[^>]+>", "", text))


class TestFooterInEveryFormat:
    def test_html(self, project, tmp_path: Path) -> None:
        from leafpress.html.renderer import HtmlRenderer

        branding, cfg, pages = project
        out = tmp_path / "o.html"
        HtmlRenderer(branding, GIT, cfg).render(pages, out)
        html = out.read_text()
        assert "Confidential &lt;b&gt;&amp;" in html  # escaped, not markup
        footer = re.search(r"<footer[^>]*>(.*?)</footer>", html, re.S)
        assert footer and _unescape(footer.group(1)).strip() == EXPECTED_FOOTER

    def test_epub(self, project, tmp_path: Path) -> None:
        from leafpress.epub.renderer import EpubRenderer

        branding, cfg, pages = project
        out = tmp_path / "o.epub"
        EpubRenderer(branding, GIT, cfg).render(pages, out)
        with zipfile.ZipFile(out) as z:
            name = next(n for n in z.namelist() if n.endswith("footer.xhtml"))
            xhtml = z.read(name).decode()
        footer = re.search(r"<footer[^>]*>(.*?)</footer>", xhtml, re.S)
        assert footer and _unescape(footer.group(1)).strip() == EXPECTED_FOOTER

    def test_odt(self, project, tmp_path: Path) -> None:
        from leafpress.odt.renderer import OdtRenderer

        branding, cfg, pages = project
        out = tmp_path / "o.odt"
        OdtRenderer(branding, GIT, cfg).render(pages, out)
        with zipfile.ZipFile(out) as z:
            styles = z.read("styles.xml").decode()
        assert EXPECTED_FOOTER in _unescape(styles)

    def test_docx(self, project, tmp_path: Path) -> None:
        from docx import Document

        from leafpress.docx.renderer import DocxRenderer

        branding, cfg, pages = project
        out = tmp_path / "o.docx"
        DocxRenderer(branding, GIT, cfg).render(pages, out)
        footer = Document(str(out)).sections[0].footer
        assert footer.paragraphs[0].text == EXPECTED_FOOTER

    def test_pdf_css(self, project) -> None:
        pytest.importorskip("weasyprint")
        from leafpress.pdf.styles import generate_pdf_css

        branding, _cfg, _pages = project
        css = generate_pdf_css(branding, GIT)
        # Shown via a CSS content string; '<', '&' need no escaping there
        assert f'content: "{EXPECTED_FOOTER}"' in css


# ---------------------------------------------------------------------------
# load_logo
# ---------------------------------------------------------------------------


def _logo_branding(logo: str) -> BrandingConfig:
    return BrandingConfig(company_name="A", project_name="B", logo_path=logo)


class TestLoadLogo:
    def test_no_logo(self) -> None:
        assert load_logo(None) is None
        assert load_logo(_logo_branding("")) is None

    def test_file_removed_after_config_load(self, tmp_path: Path) -> None:
        path = tmp_path / "logo.png"
        path.write_bytes(PNG)
        branding = _logo_branding(str(path))
        path.unlink()
        assert load_logo(branding) is None

    def test_png(self, tmp_path: Path) -> None:
        path = tmp_path / "logo.png"
        path.write_bytes(PNG)
        logo = load_logo(_logo_branding(str(path)))
        assert logo is not None and logo.data == PNG
        assert logo.mime_type == "image/png" and logo.extension == ".png"
        assert logo.data_uri().startswith("data:image/png;base64,")

    def test_misnamed_image_typed_by_content(self, tmp_path: Path) -> None:
        path = tmp_path / "logo.jpg"
        path.write_bytes(PNG)
        logo = load_logo(_logo_branding(str(path)))
        assert logo is not None and logo.mime_type == "image/png"

    def test_svg_and_svgz(self, tmp_path: Path) -> None:
        svg = tmp_path / "logo.svg"
        svg.write_text(SVG)
        svgz = tmp_path / "logo.svgz"
        svgz.write_bytes(gzip.compress(SVG.encode()))
        for path in (svg, svgz):
            logo = load_logo(_logo_branding(str(path)))
            assert logo is not None and logo.is_svg and logo.data == SVG.encode()
            assert logo.mime_type == SVG_MIME and logo.extension == ".svg"

    def test_non_image_skipped_with_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        path = tmp_path / "key.png"
        path.write_text("-----BEGIN PRIVATE KEY-----")
        with caplog.at_level(logging.WARNING):
            assert load_logo(_logo_branding(str(path))) is None
        assert "not a readable image" in caplog.text

    def test_oversized_svg_skipped(self, tmp_path: Path) -> None:
        path = tmp_path / "big.svg"
        path.write_text(SVG + " " * MAX_LOGO_BYTES)
        assert load_logo(_logo_branding(str(path))) is None

    def test_remote_logo_fetched_from_public_host_only(self) -> None:
        with patch("leafpress.downloads.download", return_value=(PNG, CaseInsensitiveDict())) as dl:
            logo = load_logo(_logo_branding("https://example.com/logo.png"))
        assert logo is not None and logo.data == PNG
        assert dl.call_args.kwargs["require_public_host"] is True
        assert dl.call_args.kwargs["max_bytes"] == MAX_LOGO_BYTES

    def test_remote_failure_skipped_with_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        with (
            patch("leafpress.downloads.download", side_effect=DownloadError("blocked host")),
            caplog.at_level(logging.WARNING),
        ):
            assert load_logo(_logo_branding("https://10.0.0.1/logo.png")) is None
        assert "Could not fetch logo" in caplog.text

    def test_remote_non_image_skipped(self) -> None:
        body = b"<html>not an image</html>"
        with patch("leafpress.downloads.download", return_value=(body, CaseInsensitiveDict())):
            assert load_logo(_logo_branding("https://example.com/logo.png")) is None


class TestLogoInEveryFormat:
    @pytest.fixture
    def setup(self, tmp_path: Path) -> tuple[BrandingConfig, MkDocsConfig]:
        logo = tmp_path / "logo.png"
        logo.write_bytes(PNG)
        docs = tmp_path / "docs"
        docs.mkdir()
        cfg = MkDocsConfig("Site", docs, [], [], None, [], tmp_path / "mkdocs.yml")
        return _logo_branding(str(logo)), cfg

    def test_epub_packages_logo_on_cover(self, setup, tmp_path: Path) -> None:
        from leafpress.epub.renderer import EpubRenderer

        branding, cfg = setup
        out = tmp_path / "o.epub"
        EpubRenderer(branding, None, cfg).render([], out)
        with zipfile.ZipFile(out) as z:
            names = z.namelist()
            logo_name = next(n for n in names if n.endswith("images/logo.png"))
            assert z.read(logo_name) == PNG
            cover = z.read(next(n for n in names if n.endswith("cover.xhtml"))).decode()
        assert 'src="images/logo.png"' in cover

    def test_html_embeds_remote_logo(self, setup, tmp_path: Path) -> None:
        import base64

        from leafpress.html.renderer import HtmlRenderer

        _branding_local, cfg = setup
        branding = _logo_branding("https://example.com/logo.png")
        out = tmp_path / "o.html"
        with patch("leafpress.downloads.download", return_value=(PNG, CaseInsensitiveDict())):
            HtmlRenderer(branding, None, cfg).render([], out)
        html = out.read_text()
        assert "https://example.com/logo.png" not in html
        assert base64.b64encode(PNG).decode() in html

    def test_docx_fetches_remote_logo_once(self, setup, tmp_path: Path) -> None:
        from leafpress.docx.renderer import DocxRenderer

        _branding_local, cfg = setup
        branding = _logo_branding("https://example.com/logo.png")
        with patch("leafpress.downloads.download", return_value=(PNG, CaseInsensitiveDict())) as dl:
            DocxRenderer(branding, None, cfg).render([], tmp_path / "o.docx")
        assert dl.call_count == 1  # header and cover share one download
        with zipfile.ZipFile(tmp_path / "o.docx") as z:
            assert any(n.startswith("word/media/") for n in z.namelist())

    def test_odt_embeds_remote_logo(self, setup, tmp_path: Path) -> None:
        from leafpress.odt.renderer import OdtRenderer

        _branding_local, cfg = setup
        branding = _logo_branding("https://example.com/logo.png")
        out = tmp_path / "o.odt"
        with patch("leafpress.downloads.download", return_value=(PNG, CaseInsensitiveDict())):
            OdtRenderer(branding, None, cfg).render([], out)
        with zipfile.ZipFile(out) as z:
            pictures = [n for n in z.namelist() if n.startswith("Pictures/")]
            assert pictures and z.read(pictures[0]) == PNG

    def test_pdf_cover_uses_data_uri(self, setup, tmp_path: Path) -> None:
        pytest.importorskip("weasyprint")
        from leafpress.pdf import renderer as pdf_renderer

        branding, cfg = setup
        captured: dict[str, str] = {}
        real_html = pdf_renderer.HTML

        def spy(*args: object, **kwargs: object) -> object:
            captured["html"] = str(kwargs.get("string", ""))
            return real_html(*args, **kwargs)

        with patch.object(pdf_renderer, "HTML", side_effect=spy):
            pdf_renderer.PdfRenderer(branding, None, cfg).render([], tmp_path / "o.pdf")
        assert "data:image/png;base64," in captured["html"]
        assert io.BytesIO((tmp_path / "o.pdf").read_bytes()).read(4) == b"%PDF"
