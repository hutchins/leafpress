"""Tests for CLI error paths and options not covered by the end-to-end suites."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from leafpress.cli import cli
from leafpress.exceptions import ConfigError, DiagramError
from leafpress.importer.base import ImportResult

runner = CliRunner()

DIAGRAM_CONFIG = """\
company_name: A
project_name: B
diagrams:
  sources:
    - url: https://example.com/a.png
      dest: docs/a.png
"""


def _flat(output: str) -> str:
    """Collapse Rich's 80-column wrapping so substrings can be matched."""
    return " ".join(output.split())


# ---------------------------------------------------------------------------
# convert
# ---------------------------------------------------------------------------


class TestConvertCommand:
    def test_leafpress_error_exits_1(self, tmp_path: Path) -> None:
        with patch("leafpress.pipeline.convert", side_effect=ConfigError("bad config")):
            result = runner.invoke(cli, ["convert", str(tmp_path)])
        assert result.exit_code == 1
        assert "bad config" in result.output

    def test_unexpected_error_exits_1_with_traceback_when_verbose(self, tmp_path: Path) -> None:
        with patch("leafpress.pipeline.convert", side_effect=ZeroDivisionError("boom")):
            quiet = runner.invoke(cli, ["convert", str(tmp_path)])
            verbose = runner.invoke(cli, ["convert", str(tmp_path), "--verbose"])
        assert quiet.exit_code == verbose.exit_code == 1
        assert "Unexpected error" in quiet.output
        assert "Traceback" not in quiet.output
        assert "Traceback" in verbose.output

    def test_no_files_generated(self, tmp_path: Path) -> None:
        with patch("leafpress.pipeline.convert", return_value=[]):
            result = runner.invoke(cli, ["convert", str(tmp_path)])
        assert result.exit_code == 0
        assert "No files were generated" in result.output

    def test_open_after_opens_each_file(self, tmp_path: Path) -> None:
        files = [tmp_path / "a.pdf", tmp_path / "a.docx"]
        with (
            patch("leafpress.pipeline.convert", return_value=files),
            patch("leafpress.cli.convert.open_file") as opener,
        ):
            result = runner.invoke(cli, ["convert", str(tmp_path), "--open"])
        assert result.exit_code == 0
        assert [c.args[0] for c in opener.call_args_list] == files

    def test_source_auto_detected(self, tmp_path: Path) -> None:
        with (
            patch("leafpress.project.detect_project", return_value=tmp_path),
            patch("leafpress.pipeline.convert", return_value=[]) as conv,
        ):
            result = runner.invoke(cli, ["convert"])
        assert result.exit_code == 0
        assert conv.call_args.kwargs["source"] == str(tmp_path)


class TestConvertFetchDiagrams:
    def test_uses_explicit_config(self, tmp_path: Path) -> None:
        cfg = tmp_path / "custom.yml"
        cfg.write_text(DIAGRAM_CONFIG)
        with (
            patch("leafpress.diagrams.fetch_diagrams", return_value=[]) as fetch,
            patch("leafpress.pipeline.convert", return_value=[]),
        ):
            runner.invoke(cli, ["convert", str(tmp_path), "-c", str(cfg), "--fetch-diagrams"])
        fetch.assert_called_once()
        assert fetch.call_args.args[1] == tmp_path.resolve()

    def test_auto_detects_leafpress_yml_in_source(self, tmp_path: Path) -> None:
        """Previously --fetch-diagrams silently did nothing without -c."""
        (tmp_path / "leafpress.yml").write_text(DIAGRAM_CONFIG)
        with (
            patch("leafpress.diagrams.fetch_diagrams", return_value=[]) as fetch,
            patch("leafpress.pipeline.convert", return_value=[]),
        ):
            runner.invoke(cli, ["convert", str(tmp_path), "--fetch-diagrams"])
        fetch.assert_called_once()

    def test_warns_when_no_config(self, tmp_path: Path) -> None:
        with (
            patch("leafpress.diagrams.fetch_diagrams") as fetch,
            patch("leafpress.pipeline.convert", return_value=[]),
        ):
            result = runner.invoke(cli, ["convert", str(tmp_path), "--fetch-diagrams"])
        fetch.assert_not_called()
        assert "no leafpress.yml found" in _flat(result.output)

    def test_warns_for_git_url_source(self) -> None:
        with (
            patch("leafpress.diagrams.fetch_diagrams") as fetch,
            patch("leafpress.pipeline.convert", return_value=[]),
        ):
            result = runner.invoke(
                cli, ["convert", "https://github.com/o/r.git", "--fetch-diagrams"]
            )
        fetch.assert_not_called()
        assert "ignored for git URL sources" in _flat(result.output)

    def test_warns_when_no_sources(self, tmp_path: Path) -> None:
        (tmp_path / "leafpress.yml").write_text("company_name: A\nproject_name: B\n")
        with (
            patch("leafpress.diagrams.fetch_diagrams") as fetch,
            patch("leafpress.pipeline.convert", return_value=[]),
        ):
            result = runner.invoke(cli, ["convert", str(tmp_path), "--fetch-diagrams"])
        fetch.assert_not_called()
        assert "no diagram sources configured" in _flat(result.output)

    def test_fetch_failure_stops_conversion(self, tmp_path: Path) -> None:
        (tmp_path / "leafpress.yml").write_text(DIAGRAM_CONFIG)
        with (
            patch("leafpress.diagrams.fetch_diagrams", side_effect=DiagramError("404")),
            patch("leafpress.pipeline.convert") as conv,
        ):
            result = runner.invoke(cli, ["convert", str(tmp_path), "--fetch-diagrams"])
        assert result.exit_code == 1
        conv.assert_not_called()


# ---------------------------------------------------------------------------
# fetch-diagrams
# ---------------------------------------------------------------------------


class TestFetchDiagramsCommand:
    def test_invalid_config_exits_1(self, tmp_path: Path) -> None:
        cfg = tmp_path / "leafpress.yml"
        cfg.write_text("company_name: [unterminated\n")
        result = runner.invoke(cli, ["fetch-diagrams", "-c", str(cfg)])
        assert result.exit_code == 1
        assert "Error" in result.output

    def test_fetch_error_exits_1(self, tmp_path: Path) -> None:
        cfg = tmp_path / "leafpress.yml"
        cfg.write_text(DIAGRAM_CONFIG)
        with patch("leafpress.diagrams.fetch_diagrams", side_effect=DiagramError("1 of 1 failed")):
            result = runner.invoke(cli, ["fetch-diagrams", "-c", str(cfg)])
        assert result.exit_code == 1
        assert "1 of 1 failed" in result.output

    def test_unexpected_error_verbose_shows_traceback(self, tmp_path: Path) -> None:
        cfg = tmp_path / "leafpress.yml"
        cfg.write_text(DIAGRAM_CONFIG)
        with patch("leafpress.diagrams.fetch_diagrams", side_effect=ZeroDivisionError("x")):
            result = runner.invoke(cli, ["fetch-diagrams", "-c", str(cfg), "--verbose"])
        assert result.exit_code == 1
        assert "Unexpected error" in result.output
        assert "Traceback" in result.output

    def test_auto_detects_config_in_cwd(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "leafpress.yaml").write_text(DIAGRAM_CONFIG)
        monkeypatch.chdir(tmp_path)
        with patch("leafpress.diagrams.fetch_diagrams", return_value=[Path("docs/a.png")]):
            result = runner.invoke(cli, ["fetch-diagrams"])
        assert result.exit_code == 0
        assert "1 diagram(s) fetched" in result.output


# ---------------------------------------------------------------------------
# import output details
# ---------------------------------------------------------------------------


def test_import_truncates_long_warning_lists(tmp_path: Path) -> None:
    src = tmp_path / "deck.pptx"
    src.write_bytes(b"x")
    result_obj = ImportResult(
        markdown_path=tmp_path / "deck.md",
        images=[tmp_path / "assets" / "i.png"],
        warnings=[f"warning {i}" for i in range(13)],
    )
    with patch("leafpress.cli.import_cmd._import_single_file", return_value=result_obj):
        result = runner.invoke(cli, ["import", str(src)])
    assert result.exit_code == 0
    assert "Images: 1 extracted" in result.output
    assert "warning 9" in result.output
    assert "warning 10" not in result.output
    assert "and 3 more" in result.output


# ---------------------------------------------------------------------------
# open-file helper
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("system", "command"), [("Darwin", "open"), ("Linux", "xdg-open")])
def test_open_file_per_platform(
    system: str, command: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sys

    from leafpress import opener

    monkeypatch.setattr(sys, "platform", "darwin" if system == "Darwin" else "linux")
    run = MagicMock()
    with (
        patch.object(opener.platform, "system", return_value=system),
        patch.object(opener.subprocess, "run", run),
    ):
        opener.open_file(tmp_path / "a.pdf")
    assert run.call_args.args[0] == [command, str(tmp_path / "a.pdf")]
