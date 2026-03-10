"""Tests for CLI commands."""

from pathlib import Path

from typer.testing import CliRunner

from leafpress.cli import cli

runner = CliRunner()


def test_version_flag() -> None:
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "leafpress version" in result.output


def test_init_command(tmp_path: Path) -> None:
    result = runner.invoke(cli, ["init", str(tmp_path)])
    assert result.exit_code == 0
    assert (tmp_path / "leafpress.yml").exists()


def test_init_no_overwrite(tmp_path: Path) -> None:
    (tmp_path / "leafpress.yml").write_text("existing")
    result = runner.invoke(cli, ["init", str(tmp_path)])
    assert result.exit_code == 1
    assert "already exists" in result.output


def test_info_command(sample_mkdocs_dir: Path) -> None:
    result = runner.invoke(cli, ["info", str(sample_mkdocs_dir)])
    assert result.exit_code == 0
    assert "Test Documentation" in result.output


def test_convert_missing_source() -> None:
    result = runner.invoke(cli, ["convert", "/nonexistent/path"])
    assert result.exit_code == 1
