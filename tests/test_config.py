"""Tests for config module."""

from pathlib import Path

import pytest
from dotenv import load_dotenv
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
    assert config.document_owner is None
    assert config.review_cycle is None


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


# --- document_owner tests ---


def test_document_owner_from_yaml(tmp_path: Path) -> None:
    """document_owner is loaded from YAML config."""
    cfg = tmp_path / "leafpress.yml"
    cfg.write_text(
        'company_name: "Test"\nproject_name: "Docs"\ndocument_owner: "Jane Smith"\n'
    )
    config = load_config(cfg)
    assert config.document_owner == "Jane Smith"


def test_document_owner_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """LEAFPRESS_DOCUMENT_OWNER env var overrides YAML."""
    for k, v in _REQUIRED.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("LEAFPRESS_DOCUMENT_OWNER", "Env Owner")
    config = config_from_env()
    assert config is not None
    assert config.document_owner == "Env Owner"


def test_document_owner_env_overrides_yaml(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Env var takes precedence over YAML value."""
    cfg = tmp_path / "leafpress.yml"
    cfg.write_text(
        'company_name: "Test"\nproject_name: "Docs"\ndocument_owner: "YAML Owner"\n'
    )
    monkeypatch.setenv("LEAFPRESS_DOCUMENT_OWNER", "Env Owner")
    config = load_config(cfg)
    assert config.document_owner == "Env Owner"


# --- review_cycle tests ---


def test_review_cycle_from_yaml(tmp_path: Path) -> None:
    """review_cycle is loaded from YAML config."""
    cfg = tmp_path / "leafpress.yml"
    cfg.write_text(
        'company_name: "Test"\nproject_name: "Docs"\nreview_cycle: "Quarterly"\n'
    )
    config = load_config(cfg)
    assert config.review_cycle == "Quarterly"


def test_review_cycle_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """LEAFPRESS_REVIEW_CYCLE env var works."""
    for k, v in _REQUIRED.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("LEAFPRESS_REVIEW_CYCLE", "Annual")
    config = config_from_env()
    assert config is not None
    assert config.review_cycle == "Annual"


def test_review_cycle_env_overrides_yaml(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Env var takes precedence over YAML value."""
    cfg = tmp_path / "leafpress.yml"
    cfg.write_text(
        'company_name: "Test"\nproject_name: "Docs"\nreview_cycle: "Quarterly"\n'
    )
    monkeypatch.setenv("LEAFPRESS_REVIEW_CYCLE", "Annual")
    config = load_config(cfg)
    assert config.review_cycle == "Annual"


# --- .env file loading tests ---


def test_dotenv_loads_config_values(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A .env file populates LEAFPRESS_* env vars for config_from_env()."""
    monkeypatch.delenv("LEAFPRESS_COMPANY_NAME", raising=False)
    monkeypatch.delenv("LEAFPRESS_PROJECT_NAME", raising=False)
    monkeypatch.delenv("LEAFPRESS_SUBTITLE", raising=False)

    env_file = tmp_path / ".env"
    env_file.write_text(
        "LEAFPRESS_COMPANY_NAME=DotenvCorp\n"
        "LEAFPRESS_PROJECT_NAME=DotenvDocs\n"
        "LEAFPRESS_SUBTITLE=From Dotenv\n"
    )
    load_dotenv(env_file, override=True)

    config = config_from_env()
    assert config is not None
    assert config.company_name == "DotenvCorp"
    assert config.project_name == "DotenvDocs"
    assert config.subtitle == "From Dotenv"


def test_dotenv_no_override_preserves_shell_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Shell env vars take priority over .env when override=False."""
    monkeypatch.setenv("LEAFPRESS_COMPANY_NAME", "ShellCorp")
    monkeypatch.setenv("LEAFPRESS_PROJECT_NAME", "ShellDocs")
    monkeypatch.delenv("LEAFPRESS_SUBTITLE", raising=False)

    env_file = tmp_path / ".env"
    env_file.write_text(
        "LEAFPRESS_COMPANY_NAME=DotenvCorp\n"
        "LEAFPRESS_PROJECT_NAME=DotenvDocs\n"
        "LEAFPRESS_SUBTITLE=From Dotenv\n"
    )
    load_dotenv(env_file, override=False)

    config = config_from_env()
    assert config is not None
    assert config.company_name == "ShellCorp"  # shell wins
    assert config.project_name == "ShellDocs"  # shell wins
    assert config.subtitle == "From Dotenv"  # .env fills the gap


def test_dotenv_missing_file_is_noop(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """load_dotenv with a nonexistent file does not crash or set values."""
    monkeypatch.delenv("LEAFPRESS_COMPANY_NAME", raising=False)
    monkeypatch.delenv("LEAFPRESS_PROJECT_NAME", raising=False)

    load_dotenv(tmp_path / ".env", override=False)
    assert config_from_env() is None
