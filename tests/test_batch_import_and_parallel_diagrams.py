"""Tests for batch import reporting and concurrent diagram fetching."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from leafpress.cli import cli
from leafpress.config import DiagramsConfig, DiagramSource
from leafpress.diagrams import fetch_diagrams
from leafpress.exceptions import DiagramError
from leafpress.importer.base import ImportResult

runner = CliRunner()

TEX = "\\documentclass{article}\\begin{document}Hello\\end{document}"


@pytest.fixture
def inputs(tmp_path: Path) -> Path:
    for sub in ("a", "b"):
        (tmp_path / sub).mkdir()
        (tmp_path / sub / "report.tex").write_text(TEX)
    (tmp_path / "a" / "other.tex").write_text(TEX)
    (tmp_path / "a" / "bad.docx").write_text("not a zip")
    return tmp_path


class TestBatchImport:
    def test_summary_table_lists_every_file(self, inputs: Path) -> None:
        out = inputs / "out"
        result = runner.invoke(
            cli,
            ["import", str(inputs / "a/bad.docx"), str(inputs / "a/other.tex"), "-o", str(out)],
        )
        assert result.exit_code == 1
        assert "Import summary" in result.output
        assert "failed" in result.output and "ok" in result.output
        assert "1 of 2 file(s) failed" in result.output
        assert (out / "other.md").exists()

    def test_error_names_the_failing_file(self, inputs: Path) -> None:
        result = runner.invoke(
            cli, ["import", str(inputs / "a/bad.docx"), "-o", str(inputs / "out")]
        )
        assert "bad.docx" in result.output.split("Error:")[1]

    def test_same_name_inputs_do_not_overwrite(self, inputs: Path) -> None:
        out = inputs / "out"
        result = runner.invoke(
            cli,
            ["import", str(inputs / "a/report.tex"), str(inputs / "b/report.tex"), "-o", str(out)],
        )
        assert result.exit_code == 1
        # Rich wraps long lines at the runner's 80 columns
        assert "would overwrite" in " ".join(result.output.split())
        assert list(out.glob("*.md")) == [out / "report.md"]

    def test_unexpected_exception_does_not_abort_batch(self, inputs: Path) -> None:
        from leafpress.cli import import_cmd as cli_mod

        real = cli_mod._import_single_file

        def flaky(file: Path, **kwargs: object) -> ImportResult:
            if file.name == "report.tex":
                raise ZeroDivisionError("boom")
            return real(file, **kwargs)  # type: ignore[arg-type]

        out = inputs / "out"
        with patch.object(cli_mod, "_import_single_file", side_effect=flaky):
            result = runner.invoke(
                cli,
                [
                    "import",
                    str(inputs / "a/report.tex"),
                    str(inputs / "a/other.tex"),
                    "-o",
                    str(out),
                ],
            )
        assert result.exit_code == 1
        assert "ZeroDivisionError" in result.output
        assert (out / "other.md").exists()

    def test_url_import_without_output_lands_in_cwd(
        self, inputs: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The download's temp dir is deleted, so the .md must not be written there."""
        workdir = inputs / "work"
        workdir.mkdir()
        monkeypatch.chdir(workdir)
        with patch("leafpress.downloads.download", return_value=(TEX.encode(), {})):
            result = runner.invoke(cli, ["import", "https://example.com/paper.tex"])
        assert result.exit_code == 0, result.output
        assert (workdir / "paper.md").exists()


def _cfg(n: int) -> DiagramsConfig:
    return DiagramsConfig(
        sources=[
            DiagramSource(url=f"https://example.com/{i}.png", dest=f"d/{i}.png") for i in range(n)
        ]
    )


class TestParallelDiagrams:
    def test_downloads_run_concurrently(self, tmp_path: Path) -> None:
        active = 0
        peak = 0
        lock = threading.Lock()

        def slow_fetch(url: str, dest: Path) -> Path:
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            time.sleep(0.1)
            with lock:
                active -= 1
            return dest

        with patch("leafpress.diagrams.fetch_url", side_effect=slow_fetch):
            result = fetch_diagrams(_cfg(8), tmp_path, refresh=True)
        assert peak > 1
        assert result == [tmp_path / f"d/{i}.png" for i in range(8)]  # config order

    def test_all_failures_reported_after_others_finish(self, tmp_path: Path) -> None:
        done: list[str] = []

        def fetch(url: str, dest: Path) -> Path:
            if url.endswith(("/1.png", "/3.png")):
                raise DiagramError("404")
            done.append(url)
            return dest

        with (
            patch("leafpress.diagrams.fetch_url", side_effect=fetch),
            pytest.raises(DiagramError) as exc_info,
        ):
            fetch_diagrams(_cfg(5), tmp_path, refresh=True)
        msg = str(exc_info.value)
        assert "2 of 5" in msg and "d/1.png" in msg and "d/3.png" in msg
        assert len(done) == 3

    def test_duplicate_dest_rejected_before_any_request(self, tmp_path: Path) -> None:
        cfg = DiagramsConfig(
            sources=[
                DiagramSource(url="https://example.com/a.png", dest="d/x.png"),
                DiagramSource(url="https://example.com/b.png", dest="d/./x.png"),
            ]
        )
        with (
            patch("leafpress.diagrams.fetch_url") as fetch,
            pytest.raises(DiagramError, match="same dest"),
        ):
            fetch_diagrams(cfg, tmp_path, refresh=True)
        fetch.assert_not_called()

    def test_missing_lucidchart_token_fails_before_any_request(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("LEAFPRESS_LUCIDCHART_TOKEN", raising=False)
        cfg = DiagramsConfig(
            sources=[
                DiagramSource(url="https://example.com/a.png", dest="d/a.png"),
                DiagramSource(lucidchart="doc123", dest="d/b.png"),
            ]
        )
        with (
            patch("leafpress.diagrams.fetch_url") as fetch,
            pytest.raises(DiagramError, match="token"),
        ):
            fetch_diagrams(cfg, tmp_path, refresh=True)
        fetch.assert_not_called()
