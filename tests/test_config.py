"""Tests for config module."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from leafpress.config import BrandingConfig, config_from_env, load_config
from leafpress.exceptions import ConfigError


def test_load_valid_config(sample_branding_config: Path) -> None:
    config = load_config(sample_branding_config)
    assert config.company_name == "Test Corp"
    assert config.project_name == "Test Documentation"
    assert config.subtitle == "Internal Docs"
    assert config.primary_color == "#336699"
    assert config.footer.include_tag is True
    assert config.footer.custom_text == "Confidential"
    assert config.pdf.page_size == "A4"


def test_load_missing_config(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_config(tmp_path / "nonexistent.yml")


def test_load_empty_config(tmp_path: Path) -> None:
    empty = tmp_path / "empty.yml"
    empty.write_text("")
    with pytest.raises(ConfigError, match="Empty config"):
        load_config(empty)


def test_config_defaults() -> None:
    config = BrandingConfig(company_name="Test", project_name="Docs")
    assert config.primary_color == "#1a73e8"
    assert config.footer.include_tag is True
    assert config.footer.include_branch is False
    assert config.pdf.page_size == "A4"
    assert config.docx.template_path is None


# --- env var tests ---

_REQUIRED = {"LEAFPRESS_COMPANY_NAME": "Env Corp", "LEAFPRESS_PROJECT_NAME": "Env Docs"}


def test_config_from_env_returns_none_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LEAFPRESS_COMPANY_NAME", raising=False)
    monkeypatch.delenv("LEAFPRESS_PROJECT_NAME", raising=False)
    assert config_from_env() is None


def test_config_from_env_requires_both_name_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEAFPRESS_COMPANY_NAME", "Env Corp")
    monkeypatch.delenv("LEAFPRESS_PROJECT_NAME", raising=False)
    assert config_from_env() is None


def test_config_from_env_builds_config(monkeypatch: pytest.MonkeyPatch) -> None:
    for k, v in _REQUIRED.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("LEAFPRESS_SUBTITLE", "Env Subtitle")
    config = config_from_env()
    assert config is not None
    assert config.company_name == "Env Corp"
    assert config.project_name == "Env Docs"
    assert config.subtitle == "Env Subtitle"


def test_env_overrides_yaml_config(
    monkeypatch: pytest.MonkeyPatch, sample_branding_config: Path
) -> None:
    monkeypatch.setenv("LEAFPRESS_COMPANY_NAME", "Override Corp")
    config = load_config(sample_branding_config)
    assert config.company_name == "Override Corp"
    # Other YAML values should be unchanged
    assert config.project_name == "Test Documentation"


def test_env_override_footer_bool(monkeypatch: pytest.MonkeyPatch) -> None:
    for k, v in _REQUIRED.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("LEAFPRESS_FOOTER_INCLUDE_BRANCH", "true")
    config = config_from_env()
    assert config is not None
    assert config.footer.include_branch is True


def test_env_override_invalid_color_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    for k, v in _REQUIRED.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("LEAFPRESS_PRIMARY_COLOR", "notacolor")
    with pytest.raises(ValidationError):
        config_from_env()
