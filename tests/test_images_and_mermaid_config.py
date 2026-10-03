"""Tests for mermaid opt-out/self-hosting, portable images in HTML/EPUB/ODT, and cleanup."""

from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

from leafpress.asset_policy import AssetPolicy
from leafpress.base_renderer import image_data_uri, rewrite_local_images
from leafpress.config import BrandingConfig, MermaidConfig, resolve_mermaid_config
from leafpress.mkdocs_parser import MkDocsConfig, NavItem


@pytest.fixture
def project(tmp_path: Path) -> Path:
    proj = tmp_path / "project"
    (proj / "docs").mkdir(parents=True)
    Image.new("RGB", (400, 200), "red").save(proj / "docs" / "wide.png")
    (proj / "docs" / "index.md").write_text("# Home\n\n![wide](wide.png)\n")
    (proj / "mkdocs.yml").write_text("site_name: Test\nnav:\n  - index.md\n")
    return proj


def _cfg(proj: Path) -> MkDocsConfig:
    return MkDocsConfig(
        site_name="Test",
        docs_dir=proj / "docs",
        nav_items=[],
        markdown_extensions=[],
        theme_name=None,
        extra_css=[],
        config_path=proj / "mkdocs.yml",
    )


def _page(proj: Path, html: str | None = None) -> list[tuple[NavItem, str]]:
    uri = (proj / "docs" / "wide.png").resolve().as_uri()
    body = html if html is not None else f'<p>Intro <img alt="wide" src="{uri}"> text</p>'
    return [(NavItem(title="Home", path=Path("index.md")), body)]


# ---------------------------------------------------------------------------
# Mermaid configuration
# ---------------------------------------------------------------------------


class TestMermaidConfig:
    def test_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("LEAFPRESS_MERMAID_ENABLED", raising=False)
        monkeypatch.delenv("LEAFPRESS_MERMAID_SERVER", raising=False)
        cfg = resolve_mermaid_config(None)
        assert cfg.enabled is True
        assert cfg.server == "https://mermaid.ink"

    def test_precedence_config_env_cli(self, monkeypatch: pytest.MonkeyPatch) -> None:
        branding = BrandingConfig(
            company_name="A",
            project_name="B",
            mermaid={"enabled": False, "server": "https://mermaid.corp.example/"},
        )
        monkeypatch.delenv("LEAFPRESS_MERMAID_ENABLED", raising=False)
        monkeypatch.delenv("LEAFPRESS_MERMAID_SERVER", raising=False)
        cfg = resolve_mermaid_config(branding)
        assert cfg.enabled is False
        assert cfg.server == "https://mermaid.corp.example"  # trailing slash stripped

        monkeypatch.setenv("LEAFPRESS_MERMAID_ENABLED", "true")
        monkeypatch.setenv("LEAFPRESS_MERMAID_SERVER", "http://localhost:3000")
        cfg = resolve_mermaid_config(branding)
        assert cfg.enabled is True
        assert cfg.server == "http://localhost:3000"

        assert resolve_mermaid_config(branding, enabled_override=False).enabled is False

    def test_env_applies_without_leafpress_yml(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LEAFPRESS_MERMAID_ENABLED", "false")
        assert resolve_mermaid_config(None).enabled is False

    def test_server_must_be_http(self) -> None:
        with pytest.raises(ValueError, match="http"):
            MermaidConfig(server="file:///etc/passwd")

    def test_render_uses_configured_server(self, tmp_path: Path) -> None:
        from leafpress.mermaid import render_mermaid

        with patch(
            "leafpress.mermaid.download", return_value=(b"PNG", {"Content-Type": "image/png"})
        ) as dl:
            render_mermaid("graph TD\n A-->B", tmp_path / "m.png", server="https://mm.corp.example")
        assert dl.call_args.args[0].startswith("https://mm.corp.example/img/")

    def test_disabled_keeps_code_and_makes_no_request(self, project: Path) -> None:
        from leafpress.markdown_renderer import MarkdownRenderer

        renderer = MarkdownRenderer(
            extensions=["pymdownx.superfences"],
            docs_dir=project / "docs",
            mermaid_output_dir=None,
            project_root=project,
        )
        with patch("leafpress.mermaid.download") as dl:
            html, _ = renderer.render(
                "```mermaid\ngraph TD\n A-->B\n```\n", project / "docs" / "index.md"
            )
        dl.assert_not_called()
        assert 'class="mermaid"' in html

    def test_cli_flag_reaches_pipeline(self, project: Path, tmp_path: Path) -> None:
        from typer.testing import CliRunner

        from leafpress.cli import cli

        with patch("leafpress.pipeline.convert", return_value=[]) as conv:
            CliRunner().invoke(
                cli,
                ["convert", str(project), "-f", "html", "--no-mermaid", "-o", str(tmp_path / "o")],
            )
        assert conv.call_args.kwargs["mermaid"] is False


# ---------------------------------------------------------------------------
# Portable images
# ---------------------------------------------------------------------------


class TestRewriteLocalImages:
    def test_outside_policy_blanked_inside_replaced(self, project: Path, tmp_path: Path) -> None:
        outside = tmp_path / "secret.png"
        Image.new("RGB", (1, 1)).save(outside)
        inside = project / "docs" / "wide.png"
        html = f'<img src="{outside.as_uri()}"><img alt="x" src="{inside.as_uri()}">'
        out = rewrite_local_images(html, AssetPolicy([project]), lambda p: "NEW")
        assert out == '<img src=""><img alt="x" src="NEW">'

    def test_non_file_srcs_untouched(self, project: Path) -> None:
        html = '<img src="https://example.com/a.png"><img src="data:image/png;base64,AA">'
        assert rewrite_local_images(html, AssetPolicy([project]), lambda p: "X") == html

    def test_data_uri(self, project: Path) -> None:
        assert image_data_uri(project / "docs" / "wide.png").startswith("data:image/png;base64,")


class TestHtmlImages:
    def test_images_embedded_as_data_uris(self, project: Path, tmp_path: Path) -> None:
        from leafpress.html.renderer import HtmlRenderer

        out = tmp_path / "out.html"
        HtmlRenderer(None, None, _cfg(project)).render(_page(project), out, cover_page=False)
        html = out.read_text()
        assert "file://" not in html
        assert 'src="data:image/png;base64,' in html


class TestEpubImages:
    def test_images_packaged_and_titles_escaped(self, project: Path, tmp_path: Path) -> None:
        from leafpress.epub.renderer import EpubRenderer

        pages = _page(project)
        pages[0] = (NavItem(title="A <b>&</b> B", path=Path("index.md")), pages[0][1])
        out = tmp_path / "out.epub"
        EpubRenderer(None, None, _cfg(project)).render(pages, out, cover_page=False)

        with zipfile.ZipFile(out) as z:
            names = z.namelist()
            chapter = next(z.read(n).decode() for n in names if n.endswith("chapter_001.xhtml"))
        assert any("/images/" in n and n.endswith(".png") for n in names)
        assert "file://" not in chapter
        assert 'src="images/' in chapter
        assert "A &lt;b&gt;&amp;&lt;/b&gt; B" in chapter


class TestOdtImages:
    def _render(self, project: Path, tmp_path: Path, html: str | None = None) -> zipfile.ZipFile:
        from leafpress.odt.renderer import OdtRenderer

        out = tmp_path / "out.odt"
        OdtRenderer(None, None, _cfg(project)).render(_page(project, html), out, cover_page=False)
        return zipfile.ZipFile(out)

    def test_inline_image_in_paragraph_embedded(self, project: Path, tmp_path: Path) -> None:
        with self._render(project, tmp_path) as z:
            assert any(n.startswith("Pictures/") for n in z.namelist())
            content = z.read("content.xml").decode()
        # 400x200 px at 96 dpi -> 4.17in x 2.08in (aspect ratio preserved)
        assert 'svg:width="4.17in"' in content
        assert 'svg:height="2.08in"' in content
        assert "Intro" in content

    def test_non_image_file_not_embedded(self, project: Path, tmp_path: Path) -> None:
        fake = project / "docs" / "notimage.png"
        fake.write_text("not really a png")
        html = f'<p><img alt="x" src="{fake.resolve().as_uri()}"></p>'
        with self._render(project, tmp_path, html) as z:
            assert not any(n.startswith("Pictures/") for n in z.namelist())


# ---------------------------------------------------------------------------
# Temp dir cleanup
# ---------------------------------------------------------------------------


class TestMermaidTempCleanup:
    def _mermaid_dirs(self) -> set[Path]:
        return set(Path(tempfile.gettempdir()).glob("leafpress-mermaid-*"))

    def test_removed_after_success(self, project: Path, tmp_path: Path) -> None:
        from leafpress.pipeline import convert

        before = self._mermaid_dirs()
        convert(str(project), tmp_path / "out", format="html", mermaid=False)
        assert self._mermaid_dirs() == before

    def test_removed_after_failure(self, project: Path, tmp_path: Path) -> None:
        from leafpress import pipeline

        before = self._mermaid_dirs()
        with (
            patch.object(pipeline, "MarkdownRenderer", side_effect=RuntimeError("boom")),
            pytest.raises(RuntimeError),
        ):
            pipeline.convert(str(project), tmp_path / "out", format="html", mermaid=False)
        assert self._mermaid_dirs() == before
