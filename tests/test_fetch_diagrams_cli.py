"""Tests for fetch-diagrams CLI command."""

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from leafpress.cli import cli
from leafpress.config import BrandingConfig, DiagramsConfig, DiagramSource

runner = CliRunner()


def test_no_config_file() -> None:
    result = runner.invoke(cli, ["fetch-diagrams", "--config", "nonexistent.yml"])
    assert result.exit_code == 1


def test_empty_diagram_sources(
    sample_branding_config: Path,
) -> None:
    """Config exists but has no diagram sources configured."""
    result = runner.invoke(cli, ["fetch-diagrams", "--config", str(sample_branding_config)])
    assert result.exit_code == 0
    assert "No diagram sources" in result.output


@patch("leafpress.diagrams.fetch_diagrams")
@patch("leafpress.config.load_config")
def test_successful_fetch(
    mock_load_config,
    mock_fetch,
    sample_branding_config: Path,
    tmp_path: Path,
) -> None:
    """Fetch succeeds with mocked diagram sources."""
    branding = BrandingConfig(
        company_name="Test",
        project_name="Test",
        diagrams=DiagramsConfig(
            sources=[DiagramSource(url="https://example.com/a.svg", dest="a.svg")]
        ),
    )
    mock_load_config.return_value = branding
    mock_fetch.return_value = [tmp_path / "a.svg"]

    result = runner.invoke(cli, ["fetch-diagrams", "--config", str(sample_branding_config)])

    assert result.exit_code == 0
    mock_fetch.assert_called_once()


@patch("leafpress.diagrams.fetch_diagrams")
@patch("leafpress.config.load_config")
def test_refresh_flag(
    mock_load_config,
    mock_fetch,
    sample_branding_config: Path,
    tmp_path: Path,
) -> None:
    branding = BrandingConfig(
        company_name="Test",
        project_name="Test",
        diagrams=DiagramsConfig(
            sources=[DiagramSource(url="https://example.com/a.svg", dest="a.svg")]
        ),
    )
    mock_load_config.return_value = branding
    mock_fetch.return_value = [tmp_path / "a.svg"]

    result = runner.invoke(
        cli,
        ["fetch-diagrams", "--config", str(sample_branding_config), "--refresh"],
    )

    assert result.exit_code == 0
    call_kwargs = mock_fetch.call_args
    assert call_kwargs.kwargs.get("refresh") is True
