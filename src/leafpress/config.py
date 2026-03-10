"""Branding configuration schema and loader."""

from __future__ import annotations

import contextlib
import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator

from leafpress.exceptions import ConfigError


class FooterConfig(BaseModel):
    """Footer configuration."""

    include_tag: bool = True
    include_date: bool = True
    include_commit: bool = True
    include_branch: bool = False
    custom_text: str | None = None
    repo_url: str | None = None


class PdfOptions(BaseModel):
    """PDF-specific options."""

    page_size: str = "A4"
    margin_top: str = "25mm"
    margin_bottom: str = "25mm"
    margin_left: str = "20mm"
    margin_right: str = "20mm"


class DocxOptions(BaseModel):
    """DOCX-specific options."""

    template_path: Path | None = None


class WatermarkConfig(BaseModel):
    """Watermark overlay configuration."""

    text: str | None = None
    color: str = "#cccccc"
    opacity: float = Field(default=0.15, ge=0.0, le=1.0)
    angle: int = Field(default=-45, ge=-90, le=90)


class BrandingConfig(BaseModel):
    """Top-level leafpress branding configuration."""

    company_name: str = Field(description="Company or organization name")
    project_name: str = Field(description="Project or document title")
    logo_path: str | None = Field(
        default=None,
        description="Path to logo image (PNG, SVG, or JPEG) or an http(s):// URL",
    )
    subtitle: str | None = None
    author: str | None = None
    author_email: str | None = None
    copyright_text: str | None = None
    primary_color: str = Field(
        default="#1a73e8",
        description="Primary brand color (hex)",
    )
    accent_color: str = Field(
        default="#ffffff",
        description="Accent/background color (hex)",
    )
    footer: FooterConfig = Field(default_factory=FooterConfig)
    pdf: PdfOptions = Field(default_factory=PdfOptions)
    docx: DocxOptions = Field(default_factory=DocxOptions)
    watermark: WatermarkConfig = Field(default_factory=WatermarkConfig)

    @field_validator("primary_color", "accent_color")
    @classmethod
    def validate_hex_color(cls, v: str) -> str:
        stripped = v.lstrip("#")
        if len(stripped) != 6 or not all(c in "0123456789abcdefABCDEF" for c in stripped):
            raise ValueError(f"Invalid hex color: {v!r} (expected 6-digit hex, e.g. #1a73e8)")
        return f"#{stripped.lower()}"

    @field_validator("logo_path")
    @classmethod
    def validate_logo_exists(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v.startswith(("http://", "https://")):
            return v
        if not Path(v).expanduser().exists():
            raise ValueError(f"Logo file not found: {v}")
        return v


_BOOL_MAP = {"true": True, "1": True, "yes": True, "false": False, "0": False, "no": False}

_STR_FIELDS = [
    ("company_name", "LEAFPRESS_COMPANY_NAME"),
    ("project_name", "LEAFPRESS_PROJECT_NAME"),
    ("logo_path", "LEAFPRESS_LOGO_PATH"),
    ("subtitle", "LEAFPRESS_SUBTITLE"),
    ("author", "LEAFPRESS_AUTHOR"),
    ("author_email", "LEAFPRESS_AUTHOR_EMAIL"),
    ("copyright_text", "LEAFPRESS_COPYRIGHT_TEXT"),
    ("primary_color", "LEAFPRESS_PRIMARY_COLOR"),
    ("accent_color", "LEAFPRESS_ACCENT_COLOR"),
]

_FOOTER_STR_FIELDS = [
    ("custom_text", "LEAFPRESS_FOOTER_CUSTOM_TEXT"),
    ("repo_url", "LEAFPRESS_FOOTER_REPO_URL"),
]

_FOOTER_BOOL_FIELDS = [
    ("include_tag", "LEAFPRESS_FOOTER_INCLUDE_TAG"),
    ("include_date", "LEAFPRESS_FOOTER_INCLUDE_DATE"),
    ("include_commit", "LEAFPRESS_FOOTER_INCLUDE_COMMIT"),
    ("include_branch", "LEAFPRESS_FOOTER_INCLUDE_BRANCH"),
]

_WATERMARK_STR_FIELDS = [
    ("text", "LEAFPRESS_WATERMARK_TEXT"),
    ("color", "LEAFPRESS_WATERMARK_COLOR"),
]


def _apply_env_overrides(config: BrandingConfig) -> BrandingConfig:
    """Override config fields with LEAFPRESS_* environment variables if set."""
    data = config.model_dump()

    for field, env in _STR_FIELDS:
        val = os.environ.get(env)
        if val:
            data[field] = val

    for field, env in _FOOTER_STR_FIELDS:
        val = os.environ.get(env)
        if val:
            data["footer"][field] = val

    for field, env in _FOOTER_BOOL_FIELDS:
        raw = os.environ.get(env, "").lower()
        if raw in _BOOL_MAP:
            data["footer"][field] = _BOOL_MAP[raw]

    for field, env in _WATERMARK_STR_FIELDS:
        val = os.environ.get(env)
        if val:
            data["watermark"][field] = val

    wm_opacity = os.environ.get("LEAFPRESS_WATERMARK_OPACITY")
    if wm_opacity:
        with contextlib.suppress(ValueError):
            data["watermark"]["opacity"] = float(wm_opacity)

    wm_angle = os.environ.get("LEAFPRESS_WATERMARK_ANGLE")
    if wm_angle:
        with contextlib.suppress(ValueError):
            data["watermark"]["angle"] = int(wm_angle)

    return BrandingConfig.model_validate(data)


def config_from_env() -> BrandingConfig | None:
    """Build a BrandingConfig solely from LEAFPRESS_* environment variables.

    Returns None if neither LEAFPRESS_COMPANY_NAME nor LEAFPRESS_PROJECT_NAME is set.
    """
    company = os.environ.get("LEAFPRESS_COMPANY_NAME")
    project = os.environ.get("LEAFPRESS_PROJECT_NAME")
    if not company or not project:
        return None
    base = BrandingConfig(company_name=company, project_name=project)
    return _apply_env_overrides(base)


def load_config(config_path: Path) -> BrandingConfig:
    """Load and validate a leafpress branding config from a YAML file."""
    try:
        with open(config_path) as f:
            raw = yaml.safe_load(f)
        if raw is None:
            raise ConfigError(f"Empty config file: {config_path}")
        logo = raw.get("logo_path")
        if logo and not str(logo).startswith(("http://", "https://")):
            expanded = Path(str(logo)).expanduser()
            if expanded.is_absolute():
                raw["logo_path"] = str(expanded)
            else:
                raw["logo_path"] = str(config_path.parent.resolve() / expanded)
        return _apply_env_overrides(BrandingConfig(**raw))
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in {config_path}: {e}") from e
    except Exception as e:
        if isinstance(e, ConfigError):
            raise
        raise ConfigError(f"Failed to load config {config_path}: {e}") from e


DEFAULT_CONFIG_TEMPLATE = """\
# leafpress branding configuration
company_name: "Your Company"
project_name: "Project Documentation"
# logo_path: "./logo.png"  # or https://example.com/logo.png
# subtitle: "Internal Documentation"
# author: "Engineering Team"
# author_email: "team@example.com"
# primary_color: "#1a73e8"
# accent_color: "#ffffff"

footer:
  include_tag: true
  include_date: true
  include_commit: true
  include_branch: false
  # custom_text: "Confidential"
  # repo_url: "https://github.com/your-org/your-repo"

pdf:
  page_size: "A4"
  margin_top: "25mm"
  margin_bottom: "25mm"
  margin_left: "20mm"
  margin_right: "20mm"

# docx:
#   template_path: null

# watermark:
#   text: "DRAFT"          # set to null or remove to disable
#   color: "#cccccc"
#   opacity: 0.15           # 0.0 to 1.0
#   angle: -45              # -90 to 90
"""
