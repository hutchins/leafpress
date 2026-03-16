"""Branding configuration schema and loader."""

from __future__ import annotations

import contextlib
import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

from leafpress.exceptions import ConfigError


class FooterConfig(BaseModel):
    """Footer configuration."""

    include_tag: bool = True
    include_date: bool = True
    include_commit: bool = True
    include_branch: bool = False
    include_render_date: bool = False
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


class DiagramSource(BaseModel):
    """A single diagram source entry."""

    url: str | None = None
    lucidchart: str | None = None
    dest: str = Field(description="Local destination path for the downloaded diagram")
    page: int = Field(default=1, ge=1, description="Page number (Lucidchart only)")

    @field_validator("dest")
    @classmethod
    def validate_dest_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Diagram dest path cannot be empty")
        return v


class DiagramsConfig(BaseModel):
    """Diagrams fetch configuration."""

    lucidchart_token: str | None = None
    cache_max_age: int = Field(
        default=3600, ge=0, description="Max age in seconds before re-downloading"
    )
    sources: list[DiagramSource] = Field(default_factory=list)


class ProjectEntry(BaseModel):
    """A sub-project in a monorepo configuration."""

    path: str | None = Field(default=None, description="Local path to mkdocs.yml dir")
    url: str | None = Field(default=None, description="Git URL to clone")
    branch: str | None = Field(default=None, description="Git branch (url only)")
    root: str | None = Field(
        default=None,
        description="Package root dir for version detection (defaults to path)",
    )
    author: str | None = None
    author_email: str | None = None
    document_owner: str | None = None
    review_cycle: str | None = None
    subtitle: str | None = None

    @model_validator(mode="after")
    def validate_source(self) -> ProjectEntry:
        if not self.path and not self.url:
            raise ValueError("Project entry must have either 'path' or 'url'")
        if self.path and self.url:
            raise ValueError("Project entry cannot have both 'path' and 'url'")
        return self


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
    document_owner: str | None = None
    review_cycle: str | None = None
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
    diagrams: DiagramsConfig = Field(default_factory=DiagramsConfig)
    projects: list[ProjectEntry] = Field(
        default_factory=list,
        description="Monorepo: list of sub-project directories containing mkdocs.yml",
    )

    @field_validator("projects", mode="before")
    @classmethod
    def normalize_projects(cls, v: list) -> list:
        """Accept both simple path strings and full dicts."""
        result = []
        for item in v:
            if isinstance(item, str):
                result.append({"path": item})
            else:
                result.append(item)
        return result

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
    ("document_owner", "LEAFPRESS_DOCUMENT_OWNER"),
    ("review_cycle", "LEAFPRESS_REVIEW_CYCLE"),
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
    ("include_render_date", "LEAFPRESS_FOOTER_INCLUDE_RENDER_DATE"),
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

    lc_token = os.environ.get("LEAFPRESS_LUCIDCHART_TOKEN")
    if lc_token:
        data.setdefault("diagrams", {})
        data["diagrams"]["lucidchart_token"] = lc_token

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


def _yaml_hint(problem: str, line: str) -> str:
    """Return a human-friendly hint based on a PyYAML problem string."""
    p = problem.lower()
    if "block end" in p and "scalar" in p:
        return (
            "Extra character after a quoted value — check for a stray quote at the end of the line."  # noqa: E501
        )
    if "mapping values are not allowed" in p:
        return "Unquoted value contains a colon — wrap the value in quotes."
    if "found character '\\t'" in p or "tab" in p:
        return "YAML does not allow tabs for indentation — use spaces instead."
    if "could not find expected ':'" in p:
        return "Missing colon after a key, or a key is incorrectly indented."
    if "found duplicate key" in p:
        return "Duplicate key in the mapping — each key must appear only once."
    if "expected <block end>" in p:
        return "Unexpected content — check indentation and that all quoted strings are closed."
    return "Check for mismatched quotes, missing colons, or incorrect indentation near this line."


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
        mark = getattr(e, "problem_mark", None)
        if mark is not None:
            lines = config_path.read_text(encoding="utf-8").splitlines()
            line_no = mark.line  # 0-indexed
            col_no = mark.column
            offending = lines[line_no] if line_no < len(lines) else ""
            caret = " " * col_no + "^"
            problem = getattr(e, "problem", str(e))
            hint = _yaml_hint(problem, offending)
            msg = (
                f"Invalid YAML in {config_path} "
                f"(line {line_no + 1}, column {col_no + 1}):\n"
                f"  {offending}\n"
                f"  {caret}\n"
                f"  {problem}\n"
                f"  Hint: {hint}"
            )
        else:
            msg = f"Invalid YAML in {config_path}: {e}"
        raise ConfigError(msg) from e
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
# document_owner: "Engineering Team"
# review_cycle: "Quarterly"
# copyright_text: "© 2025 Your Company. All rights reserved."
# primary_color: "#1a73e8"
# accent_color: "#ffffff"

footer:
  include_tag: true
  include_date: true
  include_commit: true
  include_branch: false
  include_render_date: false    # append generation date to footer
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

# diagrams:
#   lucidchart_token: null  # or set LEAFPRESS_LUCIDCHART_TOKEN env var
#   cache_max_age: 3600     # seconds; 0 = always re-download
#   sources:
#     - url: https://example.com/diagram.svg
#       dest: docs/assets/diagrams/architecture.svg
#     - lucidchart: abc123-document-id
#       dest: docs/assets/diagrams/network.png
#       page: 1

# projects:                   # monorepo: render multiple MkDocs projects as chapters
#   - services/api             # simple form: local path to mkdocs.yml directory
#   - services/frontend
#   - path: shared/docs        # detailed form with per-project metadata
#     root: shared              # package root for version detection (defaults to path)
#     author: "Docs Team"
#     author_email: "docs@example.com"
#     document_owner: "Jane Smith"
#     review_cycle: "Quarterly"
#     subtitle: "Shared Libraries"
#   - url: https://github.com/org/repo  # remote git repo
#     branch: main
#     author: "Platform Team"
"""
