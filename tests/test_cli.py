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


def test_convert_pdf(sample_mkdocs_dir: Path, tmp_output: Path) -> None:
    result = runner.invoke(
        cli,
        ["convert", str(sample_mkdocs_dir), "-f", "pdf", "-o", str(tmp_output)],
    )
    assert result.exit_code == 0
    assert list(tmp_output.glob("*.pdf"))


def test_convert_with_watermark(sample_mkdocs_dir: Path, tmp_output: Path) -> None:
    result = runner.invoke(
        cli,
        [
            "convert", str(sample_mkdocs_dir),
            "-f", "pdf", "-o", str(tmp_output),
            "--watermark", "DRAFT",
        ],
    )
    assert result.exit_code == 0


def test_convert_with_local_time(sample_mkdocs_dir: Path, tmp_output: Path) -> None:
    result = runner.invoke(
        cli,
        [
            "convert", str(sample_mkdocs_dir),
            "-f", "pdf", "-o", str(tmp_output),
            "--local-time",
        ],
    )
    assert result.exit_code == 0


def test_convert_no_cover_no_toc(sample_mkdocs_dir: Path, tmp_output: Path) -> None:
    result = runner.invoke(
        cli,
        [
            "convert", str(sample_mkdocs_dir),
            "-f", "pdf", "-o", str(tmp_output),
            "--no-cover-page", "--no-toc",
        ],
    )
    assert result.exit_code == 0


def test_info_nonexistent_source() -> None:
    result = runner.invoke(cli, ["info", "/nonexistent/path"])
    assert result.exit_code == 1
