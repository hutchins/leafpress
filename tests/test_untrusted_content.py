"""Security tests for rendering content from untrusted repositories.

A cloned git source, a monorepo ``projects[].url`` entry, or a CI checkout of
a contributor's branch controls mkdocs.yml, leafpress.yml, .env, and every
Markdown file. None of those should be able to read files outside the
project, reach internal network hosts, or change how git runs.
"""

from __future__ import annotations

import os
import socket
from email.message import EmailMessage
from pathlib import Path
from urllib.error import HTTPError

import pytest

from leafpress.asset_policy import AssetPolicy, file_uri_to_path, is_public_http_url
from leafpress.config import BrandingConfig, WatermarkConfig
from leafpress.exceptions import ConfigError, SourceError
from leafpress.markdown_renderer import MarkdownRenderer, _is_extension_class_ref
from leafpress.mkdocs_parser import MkDocsConfig, NavItem, parse_mkdocs_config, resolve_page_path
from leafpress.pdf.styles import _css_string_escape, generate_pdf_css
from leafpress.pipeline import _collect_monorepo_pages, _load_project_env

SECRET = "TOP-SECRET-MARKER-9f2c"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A project dir with docs/, plus a secret file *outside* the project."""
    (tmp_path / "secret.txt").write_text(SECRET)
    proj = tmp_path / "project"
    (proj / "docs").mkdir(parents=True)
    (proj / "docs" / "index.md").write_text("# Home\n")
    return proj


def _mkdocs_cfg(proj: Path) -> MkDocsConfig:
    return MkDocsConfig(
        site_name="Test",
        docs_dir=proj / "docs",
        nav_items=[],
        markdown_extensions=[],
        theme_name=None,
        extra_css=[],
        config_path=proj / "mkdocs.yml",
    )


# ---------------------------------------------------------------------------
# .env handling
# ---------------------------------------------------------------------------


class TestProjectEnv:
    def test_only_leafpress_keys_are_loaded(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("LEAFPRESS_COMPANY_NAME", raising=False)
        monkeypatch.delenv("GIT_SSH_COMMAND", raising=False)
        env = tmp_path / ".env"
        env.write_text("LEAFPRESS_COMPANY_NAME=Acme\nGIT_SSH_COMMAND=touch /tmp/pwned\n")

        _load_project_env(env)

        assert os.environ["LEAFPRESS_COMPANY_NAME"] == "Acme"
        assert "GIT_SSH_COMMAND" not in os.environ
        monkeypatch.delenv("LEAFPRESS_COMPANY_NAME")

    def test_shell_env_takes_priority(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("LEAFPRESS_COMPANY_NAME", "FromShell")
        env = tmp_path / ".env"
        env.write_text("LEAFPRESS_COMPANY_NAME=FromDotenv\n")

        _load_project_env(env)

        assert os.environ["LEAFPRESS_COMPANY_NAME"] == "FromShell"

    def test_missing_file_is_ignored(self, tmp_path: Path) -> None:
        _load_project_env(tmp_path / ".env")

    def test_cloned_source_env_is_not_loaded(
        self, project: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A .env in a cloned (temporary) repo must be ignored entirely."""
        from leafpress import pipeline

        (project / ".env").write_text("LEAFPRESS_COMPANY_NAME=Evil\n")
        (project / "mkdocs.yml").write_text("site_name: T\nnav:\n  - index.md\n")
        monkeypatch.delenv("LEAFPRESS_COMPANY_NAME", raising=False)
        monkeypatch.setattr(pipeline, "resolve_source", lambda *a, **k: _NoCleanup(project))

        pipeline.convert(
            source="https://example.com/repo.git",
            output_dir=project / "out",
            format="markdown",
        )

        assert "LEAFPRESS_COMPANY_NAME" not in os.environ


class _NoCleanup:
    """ResolvedSource stand-in that reports a clone but doesn't delete it."""

    is_temporary = True

    def __init__(self, path: Path) -> None:
        self.path = path

    def __enter__(self) -> Path:
        return self.path

    def __exit__(self, *args: object) -> None:
        pass


# ---------------------------------------------------------------------------
# mkdocs.yml: docs_dir and nav confinement
# ---------------------------------------------------------------------------


class TestPageConfinement:
    def test_docs_dir_outside_project_rejected(self, project: Path) -> None:
        cfg = project / "mkdocs.yml"
        cfg.write_text(f"site_name: T\ndocs_dir: {project.parent}\n")
        with pytest.raises(ConfigError, match="inside the project"):
            parse_mkdocs_config(cfg)

    def test_nav_traversal_entries_dropped(self, project: Path) -> None:
        cfg = project / "mkdocs.yml"
        cfg.write_text(
            "site_name: T\nnav:\n  - index.md\n  - Secret: ../../secret.txt\n  - /etc/passwd\n"
        )
        parsed = parse_mkdocs_config(cfg)
        assert [str(i.path) for i in parsed.nav_items] == ["index.md"]

    def test_symlinked_page_outside_docs_dir_rejected(self, project: Path) -> None:
        link = project / "docs" / "leak.md"
        link.symlink_to(project.parent / "secret.txt")
        assert resolve_page_path(project / "docs", Path("leak.md")) is None
        assert resolve_page_path(project / "docs", Path("index.md")) is not None

    def test_markdown_export_skips_symlink_escape(self, project: Path) -> None:
        from leafpress.markdown_export.renderer import MarkdownExportRenderer

        (project / "docs" / "leak.md").symlink_to(project.parent / "secret.txt")
        cfg = _mkdocs_cfg(project)
        out = project / "out.md"
        MarkdownExportRenderer(None, None, cfg).render(
            [(NavItem(title="Leak", path=Path("leak.md")), "")], out
        )
        assert SECRET not in out.read_text()


# ---------------------------------------------------------------------------
# Markdown extensions configured by mkdocs.yml
# ---------------------------------------------------------------------------


class TestExtensionConfig:
    def test_snippets_cannot_escape_project(self, project: Path) -> None:
        renderer = MarkdownRenderer(
            extensions=[
                {
                    "pymdownx.snippets": {
                        "base_path": ["/", str(project.parent)],
                        "restrict_base_path": False,
                        "url_download": True,
                    }
                }
            ],
            docs_dir=project / "docs",
            project_root=project,
        )
        md = f'--8<-- "{project.parent / "secret.txt"}"\n\n--8<-- "../secret.txt"\n'
        html, _ = renderer.render(md, project / "docs" / "index.md")

        assert SECRET not in html
        assert any("restrict_base_path" in w for w in renderer.config_warnings)
        assert any("url_download" in w for w in renderer.config_warnings)

    def test_snippets_default_is_project_root_not_cwd(
        self, project: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A bare `pymdownx.snippets` must not read relative to the current directory."""
        monkeypatch.chdir(project.parent)
        renderer = MarkdownRenderer(
            extensions=["pymdownx.snippets"],
            docs_dir=project / "docs",
            project_root=project,
        )
        html, _ = renderer.render('--8<-- "secret.txt"\n', project / "docs" / "index.md")
        assert SECRET not in html

    def test_snippets_inside_project_still_work(
        self, project: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (project / "includes").mkdir()
        (project / "includes" / "abbr.md").write_text("INCLUDED-OK")
        monkeypatch.chdir(project.parent)  # relative base_path resolves from project root
        renderer = MarkdownRenderer(
            extensions=[{"pymdownx.snippets": {"base_path": ["includes"]}}],
            docs_dir=project / "docs",
            project_root=project,
        )
        html, _ = renderer.render('--8<-- "abbr.md"\n', project / "docs" / "index.md")
        assert "INCLUDED-OK" in html
        assert renderer.config_warnings == []

    def test_class_ref_must_be_markdown_extension(self) -> None:
        assert not _is_extension_class_ref("subprocess:Popen")
        assert not _is_extension_class_ref("os:system")
        assert not _is_extension_class_ref("no_such_module_xyz:Thing")
        assert _is_extension_class_ref("markdown.extensions.toc:TocExtension")
        assert _is_extension_class_ref("pymdownx.snippets")

    def test_non_extension_class_is_not_instantiated(self, project: Path) -> None:
        marker = project / "pwned"
        renderer = MarkdownRenderer(
            extensions=[{"subprocess:Popen": {"args": ["touch", str(marker)]}}],
            docs_dir=project / "docs",
            project_root=project,
        )
        assert not marker.exists()
        assert ("subprocess:Popen", False) in [
            (e, ok) for e, ok, _ in renderer.extension_load_results
        ]


# ---------------------------------------------------------------------------
# Asset references in rendered HTML
# ---------------------------------------------------------------------------


class TestAssetReferences:
    def _render(self, project: Path, md: str) -> tuple[str, MarkdownRenderer]:
        renderer = MarkdownRenderer(extensions=[], docs_dir=project / "docs", project_root=project)
        html, _ = renderer.render(md, project / "docs" / "index.md")
        return html, renderer

    def test_relative_image_outside_project_blanked(self, project: Path) -> None:
        html, renderer = self._render(project, "![x](../../secret.txt)\n")
        assert 'src=""' in html
        assert any("blocked" in ref for _, ref in renderer.unresolved_assets)

    def test_raw_html_file_uri_outside_project_blanked(self, project: Path) -> None:
        uri = (project.parent / "secret.txt").as_uri()
        html, _ = self._render(project, f'<img src="{uri}">\n')
        assert uri not in html

    def test_image_inside_project_rewritten(self, project: Path) -> None:
        (project / "docs" / "pic.png").write_bytes(b"\x89PNG")
        html, renderer = self._render(project, "![x](pic.png)\n")
        assert (project / "docs" / "pic.png").resolve().as_uri() in html
        assert renderer.unresolved_assets == []

    def test_links_outside_project_left_alone(self, project: Path) -> None:
        html, renderer = self._render(project, "[x](../../secret.txt)\n")
        assert 'href="../../secret.txt"' in html
        assert renderer.unresolved_assets == []

    def test_data_uri_not_reported_missing(self, project: Path) -> None:
        _, renderer = self._render(project, '<img src="data:image/png;base64,AAAA">\n')
        assert renderer.unresolved_assets == []


class TestAssetPolicy:
    def test_file_uri_to_path_decodes_percent_encoding(self, tmp_path: Path) -> None:
        p = tmp_path / "with space.png"
        assert file_uri_to_path(p.as_uri()) == p
        assert file_uri_to_path("https://example.com/x.png") is None

    def test_allows_roots_and_files_only(self, project: Path) -> None:
        logo = project.parent / "logo.png"
        policy = AssetPolicy([project], files=[logo])
        assert policy.allows(project / "docs" / "index.md")
        assert policy.allows(logo)
        assert not policy.allows(project.parent / "secret.txt")
        assert not policy.allows(project / ".." / "secret.txt")

    def test_symlink_escape_blocked(self, project: Path) -> None:
        link = project / "docs" / "img.png"
        link.symlink_to(project.parent / "secret.txt")
        assert not AssetPolicy([project]).allows(link)


class TestImageEmbedding:
    def test_odt_skips_image_outside_project(self, project: Path) -> None:
        from bs4 import BeautifulSoup
        from odf.opendocument import OpenDocumentText

        from leafpress.odt.renderer import OdtRenderer

        renderer = OdtRenderer(None, None, _mkdocs_cfg(project))
        doc = OpenDocumentText()
        img = BeautifulSoup(
            f'<img src="{(project.parent / "secret.txt").as_uri()}">', "html.parser"
        ).img
        renderer._process_element(doc, img)
        assert not doc.Pictures

    def test_docx_skips_image_outside_project(
        self, project: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        from docx import Document

        from leafpress.docx.html_converter import HtmlToDocxConverter

        doc = Document()
        conv = HtmlToDocxConverter(doc, project / "docs", AssetPolicy([project]))
        conv.convert(f'<img src="{(project.parent / "secret.txt").as_uri()}">')
        assert "outside the project" in caplog.text


# ---------------------------------------------------------------------------
# WeasyPrint fetcher
# ---------------------------------------------------------------------------


def _fetcher(project: Path):
    pytest.importorskip("weasyprint", exc_type=OSError)
    from leafpress.pdf.url_fetcher import RestrictedURLFetcher

    return RestrictedURLFetcher(AssetPolicy([project]))


class TestPdfFetcher:
    def test_blocks_file_outside_project(self, project: Path) -> None:
        with pytest.raises(ValueError, match="outside the project"):
            _fetcher(project).fetch((project.parent / "secret.txt").as_uri())

    def test_allows_file_inside_project(self, project: Path) -> None:
        resp = _fetcher(project).fetch((project / "docs" / "index.md").as_uri())
        assert resp.read() == b"# Home\n"

    def test_blocks_unknown_schemes(self, project: Path) -> None:
        with pytest.raises(ValueError, match="scheme"):
            _fetcher(project).fetch("ftp://example.com/x")

    def test_blocks_internal_hosts(self, project: Path) -> None:
        fetcher = _fetcher(project)
        for url in (
            "http://127.0.0.1/",
            "http://169.254.169.254/latest/meta-data/",
            "http://10.0.0.1/",
            "http://[::1]/",
        ):
            with pytest.raises(ValueError, match="non-public"):
                fetcher.fetch(url)

    def test_redirect_to_internal_host_blocked(
        self, project: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from weasyprint.urls import URLFetcher

        fetcher = _fetcher(project)
        monkeypatch.setattr(
            socket, "getaddrinfo", lambda host, *a: [(0, 0, 0, "", ("93.184.216.34", 0))]
        )
        headers = EmailMessage()
        headers["Location"] = "http://169.254.169.254/latest/"

        def fake_fetch(self, url, headers_=None):
            raise HTTPError(url, 302, "Found", headers, None)

        monkeypatch.setattr(URLFetcher, "fetch", fake_fetch)
        monkeypatch.setattr(
            "leafpress.pdf.url_fetcher.is_public_http_url",
            lambda url: "169.254" not in url,
        )
        with pytest.raises(ValueError, match="non-public"):
            fetcher.fetch("http://example.com/img.png")

    def test_public_url_check(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            socket, "getaddrinfo", lambda host, *a: [(0, 0, 0, "", ("93.184.216.34", 0))]
        )
        assert is_public_http_url("https://example.com/x.png")
        assert not is_public_http_url("file:///etc/passwd")


# ---------------------------------------------------------------------------
# Branding values interpolated into CSS
# ---------------------------------------------------------------------------


class TestCssInjection:
    def test_css_string_escape_handles_backslash(self) -> None:
        # A trailing backslash must not be able to escape the closing quote.
        assert _css_string_escape('x\\"') == 'x\\\\\\"'
        assert _css_string_escape("a\nb") == "a\\A b"

    def test_footer_text_cannot_break_out(self) -> None:
        branding = BrandingConfig(
            company_name="Acme",
            project_name="Docs",
            footer={"custom_text": 'x\\"; } @import url("file:///etc/passwd"); .a { content: "'},
        )
        css = generate_pdf_css(branding, None)
        assert '\\\\\\"; } @import' in css

    def test_watermark_color_must_be_hex(self) -> None:
        with pytest.raises(ValueError):
            WatermarkConfig(text="DRAFT", color="red; } @import url(file:///etc/passwd)")
        assert WatermarkConfig(color="#ABCDEF").color == "#abcdef"


# ---------------------------------------------------------------------------
# Monorepo configs from cloned repos
# ---------------------------------------------------------------------------


class TestMonorepoConfinement:
    def test_untrusted_local_path_cannot_escape(self, project: Path) -> None:
        from rich.console import Console

        from leafpress.config import ProjectEntry

        outside = project.parent / "other"
        (outside / "docs").mkdir(parents=True)
        (outside / "mkdocs.yml").write_text("site_name: Other\n")
        branding = BrandingConfig(company_name="A", project_name="B")
        with pytest.raises(SourceError, match="escapes"):
            _collect_monorepo_pages(
                [ProjectEntry(path="../other")],
                project,
                project / "mermaid",
                branding,
                Console(quiet=True),
                untrusted_source=True,
            )
