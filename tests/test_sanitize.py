"""Tests for HTML sanitizing of untrusted page content."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from leafpress.sanitize import sanitize_html, should_sanitize

XSS_VECTORS = [
    "<script>alert(1)</script>",
    '<img src="x.png" onerror="alert(1)">',
    '<a href="javascript:alert(1)">x</a>',
    '<a href="data:text/html;base64,PHNjcmlwdD4=">x</a>',
    '<iframe src="https://evil.example"></iframe>',
    '<object data="x.swf"></object>',
    '<embed src="x.swf">',
    '<svg onload="alert(1)"><circle/></svg>',
    '<form action="https://evil.example"><input type="text" name="q"></form>',
    '<p style="background-image:url(https://track.example/p.gif)">x</p>',
    "<style>body{display:none}</style>",
    '<meta http-equiv="refresh" content="0;url=https://evil.example">',
    '<base href="https://evil.example/">',
    '<details ontoggle="alert(1)" open>x</details>',
]


@pytest.mark.parametrize("payload", XSS_VECTORS)
def test_active_content_removed(payload: str) -> None:
    out = sanitize_html(payload).lower()
    for needle in (
        "<script",
        "onerror",
        "onload",
        "ontoggle",
        "javascript:",
        "data:text/html",
        "<iframe",
        "<object",
        "<embed",
        "<svg",
        "<form",
        "url(",
        "<style",
        "<meta",
        "<base",
        'type="text"',
    ):
        assert needle not in out, (payload, out)


@pytest.mark.parametrize(
    "html",
    [
        '<div class="admonition note"><p class="admonition-title">Note</p><p>Body</p></div>',
        '<details class="tip" open><summary>More</summary><p>Hidden</p></details>',
        '<table><thead><tr><th align="left">A</th></tr></thead>'
        '<tbody><tr><td colspan="2">1</td></tr></tbody></table>',
        '<ul class="task-list"><li class="task-list-item">'
        '<input type="checkbox" disabled checked> done</li></ul>',
        '<div class="tabbed-set" data-tabs="1:2"><input checked id="__tabbed_1_1" '
        'name="__tabbed_1" type="radio"><label for="__tabbed_1_1">A</label></div>',
        '<div class="highlight"><pre><span></span><code><span class="k">def</span> '
        "f():</code></pre></div>",
        '<p>See<sup id="fnref:1"><a class="footnote-ref" href="#fn:1">1</a></sup></p>',
        '<img alt="Mermaid diagram" src="file:///tmp/leafpress-mermaid-x/m.png">',
        '<img alt="inline" src="data:image/png;base64,iVBORw0KGgo=">',
        '<a href="https://example.com">link</a> <a href="mailto:a@b.c">mail</a>',
        '<h2 id="section">Section</h2><p><mark>hi</mark> <kbd>Ctrl</kbd> <del>x</del></p>',
    ],
)
def test_normal_mkdocs_markup_preserved(html: str) -> None:
    from bs4 import BeautifulSoup

    before = BeautifulSoup(html, "html.parser")
    after = BeautifulSoup(sanitize_html(html), "html.parser")
    assert [t.name for t in after.find_all()] == [t.name for t in before.find_all()]
    for b, a in zip(before.find_all(), after.find_all(), strict=True):
        assert set(a.attrs) == set(b.attrs), (b, a)


def test_safe_inline_styles_kept() -> None:
    out = sanitize_html('<img src="x.png" style="max-width: 100%; position: fixed">')
    assert "max-width:100%" in out
    assert "position" not in out


class TestShouldSanitize:
    def test_precedence(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("LEAFPRESS_SANITIZE_HTML", raising=False)
        assert (
            should_sanitize(cli_override=None, untrusted_source=False, config_value=False) is False
        )
        assert should_sanitize(cli_override=None, untrusted_source=False, config_value=True) is True
        # Cloned sources are always sanitized, whatever their own leafpress.yml says
        assert should_sanitize(cli_override=None, untrusted_source=True, config_value=False) is True
        # The operator can still override explicitly
        assert (
            should_sanitize(cli_override=False, untrusted_source=True, config_value=True) is False
        )
        monkeypatch.setenv("LEAFPRESS_SANITIZE_HTML", "false")
        assert should_sanitize(cli_override=None, untrusted_source=True, config_value=True) is False
        monkeypatch.setenv("LEAFPRESS_SANITIZE_HTML", "1")
        assert (
            should_sanitize(cli_override=None, untrusted_source=False, config_value=False) is True
        )


class TestPipelineIntegration:
    @pytest.fixture
    def project(self, tmp_path: Path) -> Path:
        proj = tmp_path / "p"
        (proj / "docs").mkdir(parents=True)
        (proj / "mkdocs.yml").write_text("site_name: P\nnav:\n  - index.md\n")
        (proj / "docs" / "index.md").write_text(
            "# Hi\n\n<img src=x onerror=alert(1)>\n\n<script>alert(2)</script>\n"
        )
        return proj

    def test_local_source_unsanitized_by_default(
        self, project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from leafpress.pipeline import convert

        monkeypatch.delenv("LEAFPRESS_SANITIZE_HTML", raising=False)
        convert(str(project), tmp_path / "o", format="html", mermaid=False)
        assert "alert(2)" in (tmp_path / "o" / "P.html").read_text()

    def test_flag_sanitizes_local_source(self, project: Path, tmp_path: Path) -> None:
        from leafpress.pipeline import convert

        convert(str(project), tmp_path / "o", format="html", mermaid=False, sanitize_html=True)
        html = (tmp_path / "o" / "P.html").read_text()
        assert "alert(" not in html
        assert "onerror" not in html

    def test_cloned_source_sanitized_even_if_config_disables(
        self, project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from leafpress import pipeline

        monkeypatch.delenv("LEAFPRESS_SANITIZE_HTML", raising=False)
        (project / "leafpress.yml").write_text(
            "company_name: A\nproject_name: P\nsanitize_html: false\n"
        )

        class _Clone:
            is_temporary = True

            def __enter__(self) -> Path:
                return project

            def __exit__(self, *a: object) -> None:
                pass

        with patch.object(pipeline, "resolve_source", return_value=_Clone()):
            pipeline.convert(
                "https://example.com/r.git", tmp_path / "o", format="html", mermaid=False
            )
        assert "alert(" not in (tmp_path / "o" / "P.html").read_text()

    def test_cli_flag_reaches_pipeline(self, project: Path, tmp_path: Path) -> None:
        from typer.testing import CliRunner

        from leafpress.cli import cli

        with patch("leafpress.pipeline.convert", return_value=[]) as conv:
            CliRunner().invoke(
                cli, ["convert", str(project), "--sanitize-html", "-o", str(tmp_path / "o")]
            )
        assert conv.call_args.kwargs["sanitize_html"] is True
