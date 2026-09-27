"""Cross-format watermark checks and console log-level configuration."""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest
from rich.console import Console

from leafpress.pipeline import _resolve_log_level, convert

MARK = "DRAFT <b>&</b>"


@pytest.fixture(scope="module")
def outputs(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Convert one small project to every format with a watermark containing markup."""
    root = tmp_path_factory.mktemp("wm")
    (root / "p" / "docs").mkdir(parents=True)
    (root / "p" / "mkdocs.yml").write_text("site_name: P\n")
    (root / "p" / "docs" / "index.md").write_text("# Hi\n\nBody\n")
    convert(str(root / "p"), root / "out", format="all", watermark=MARK, mermaid=False)
    return root / "out"


def _zip_text(path: Path, pattern: str) -> str:
    with zipfile.ZipFile(path) as z:
        return "\n".join(z.read(n).decode() for n in z.namelist() if re.search(pattern, n))


class TestWatermarkAcrossFormats:
    def test_html(self, outputs: Path) -> None:
        html = (outputs / "P.html").read_text()
        assert 'class="lp-watermark">DRAFT &lt;b&gt;&amp;&lt;/b&gt;</div>' in html
        assert "<b>&</b>" not in html

    def test_epub(self, outputs: Path) -> None:
        chapters = _zip_text(outputs / "P.epub", r"chapter_\d+\.xhtml$")
        assert 'class="lp-watermark">DRAFT &lt;b&gt;&amp;&lt;/b&gt;</div>' in chapters

    def test_docx(self, outputs: Path) -> None:
        header = _zip_text(outputs / "P.docx", r"word/header\d*\.xml$")
        match = re.search(r"<v:textpath ([^>]*)/>", header)
        assert match, header
        attrs = match.group(1)
        assert 'string="DRAFT &lt;b&gt;&amp;&lt;/b&gt;"' in attrs
        # The font name must reach Word as "Calibri", not a double-escaped &amp;quot;
        assert "&amp;quot;" not in attrs
        assert 'style="font-family:&quot;Calibri&quot;;font-size:1pt"' in attrs

    def test_odt(self, outputs: Path) -> None:
        content = _zip_text(outputs / "P.odt", r"^content\.xml$")
        assert "DRAFT &lt;b&gt;&amp;&lt;/b&gt;" in content

    def test_pdf(self, outputs: Path) -> None:
        if not shutil.which("pdftotext"):
            pytest.skip("pdftotext (poppler) not installed")
        text = subprocess.run(
            ["pdftotext", "-raw", str(outputs / "P.pdf"), "-"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        # The rotated watermark is extracted in fragments; compare without whitespace
        assert "DRAFT<b>&</b>" in "".join(text.split())

    def test_markdown_export_has_no_watermark(self, outputs: Path) -> None:
        assert "DRAFT" not in (outputs / "P.md").read_text()


class TestLogLevel:
    def _console(self) -> Console:
        return Console(record=True, width=200)

    def test_default_is_warning(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("LEAFPRESS_LOG_LEVEL", raising=False)
        assert _resolve_log_level(False, self._console()) == logging.WARNING

    @pytest.mark.parametrize(
        ("value", "level"),
        [("debug", logging.DEBUG), ("INFO", logging.INFO), (" error ", logging.ERROR)],
    )
    def test_env_sets_level(self, value: str, level: int, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LEAFPRESS_LOG_LEVEL", value)
        assert _resolve_log_level(False, self._console()) == level

    def test_verbose_wins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LEAFPRESS_LOG_LEVEL", "ERROR")
        assert _resolve_log_level(True, self._console()) == logging.DEBUG

    def test_invalid_value_warns(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LEAFPRESS_LOG_LEVEL", "LOUD")
        con = self._console()
        assert _resolve_log_level(False, con) == logging.WARNING
        assert "Ignoring invalid LEAFPRESS_LOG_LEVEL=LOUD" in con.export_text()

    def test_info_messages_shown_when_enabled(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        (tmp_path / "p" / "docs").mkdir(parents=True)
        (tmp_path / "p" / "mkdocs.yml").write_text("site_name: P\n")
        (tmp_path / "p" / "docs" / "index.md").write_text("# Hi\n")

        def emit_info(*args: object, **kwargs: object) -> list[Path]:
            logging.getLogger("leafpress.test").info("hello-from-info")
            return []

        monkeypatch.setattr("leafpress.pipeline.extract_git_info", lambda *_: emit_info() or None)

        monkeypatch.setenv("LEAFPRESS_LOG_LEVEL", "INFO")
        convert(str(tmp_path / "p"), tmp_path / "o", format="markdown", mermaid=False)
        assert "hello-from-info" in capsys.readouterr().out

        monkeypatch.delenv("LEAFPRESS_LOG_LEVEL")
        convert(str(tmp_path / "p"), tmp_path / "o", format="markdown", mermaid=False)
        assert "hello-from-info" not in capsys.readouterr().out
