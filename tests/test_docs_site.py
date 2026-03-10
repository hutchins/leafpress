"""Tests for the MkDocs documentation site in docs/.

Validates that the mkdocs.yml config is consistent, all referenced pages exist,
internal links resolve, and required content is present.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from leafpress.mkdocs_parser import _MkDocsLoader

DOCS_ROOT = Path(__file__).parent.parent / "docs"
MKDOCS_YML = DOCS_ROOT / "mkdocs.yml"
DOCS_DIR = DOCS_ROOT / "docs"


@pytest.fixture(scope="module")
def mkdocs_config() -> dict:
    """Load and return the parsed mkdocs.yml."""
    assert MKDOCS_YML.exists(), f"mkdocs.yml not found at {MKDOCS_YML}"
    with open(MKDOCS_YML) as f:
        return yaml.load(f, Loader=_MkDocsLoader)


def _extract_nav_paths(nav: list) -> list[str]:
    """Recursively extract all .md file paths from the nav structure."""
    paths = []
    for item in nav:
        if isinstance(item, str):
            paths.append(item)
        elif isinstance(item, dict):
            for value in item.values():
                if isinstance(value, str):
                    paths.append(value)
                elif isinstance(value, list):
                    paths.extend(_extract_nav_paths(value))
    return paths


# ---------------------------------------------------------------------------
# mkdocs.yml structure
# ---------------------------------------------------------------------------


class TestMkDocsConfig:
    """Validate mkdocs.yml is well-formed and consistent."""

    def test_mkdocs_yml_exists(self) -> None:
        assert MKDOCS_YML.exists()

    def test_has_required_fields(self, mkdocs_config: dict) -> None:
        """Config has all required top-level fields."""
        for field in ("site_name", "nav", "theme", "repo_url"):
            assert field in mkdocs_config, f"Missing required field: {field}"

    def test_site_name(self, mkdocs_config: dict) -> None:
        assert mkdocs_config["site_name"] == "LeafPress"

    def test_theme_is_material(self, mkdocs_config: dict) -> None:
        assert mkdocs_config["theme"]["name"] == "material"

    def test_nav_is_not_empty(self, mkdocs_config: dict) -> None:
        assert len(mkdocs_config["nav"]) > 0

    def test_docs_dir_exists(self, mkdocs_config: dict) -> None:
        docs_dir = mkdocs_config.get("docs_dir", "docs")
        assert (DOCS_ROOT / docs_dir).is_dir()


# ---------------------------------------------------------------------------
# Nav pages all exist on disk
# ---------------------------------------------------------------------------


class TestNavPagesExist:
    """Every page referenced in nav must exist as a file."""

    def test_all_nav_pages_exist(self, mkdocs_config: dict) -> None:
        nav_paths = _extract_nav_paths(mkdocs_config["nav"])
        missing = []
        for path in nav_paths:
            full_path = DOCS_DIR / path
            if not full_path.exists():
                missing.append(path)
        assert not missing, f"Nav references missing files: {missing}"

    def test_no_orphan_markdown_files(self, mkdocs_config: dict) -> None:
        """Every .md file in docs/ should be referenced in nav (except 404.md)."""
        nav_paths = set(_extract_nav_paths(mkdocs_config["nav"]))
        md_files = {
            p.relative_to(DOCS_DIR).as_posix()
            for p in DOCS_DIR.rglob("*.md")
        }
        excluded = {"404.md"}
        orphans = md_files - nav_paths - excluded
        assert not orphans, f"Markdown files not in nav: {orphans}"


# ---------------------------------------------------------------------------
# Internal links resolve
# ---------------------------------------------------------------------------


class TestInternalLinks:
    """Validate that internal markdown links point to existing files."""

    # Matches [text](target.md) and [text](target.md#anchor) but not http(s) URLs
    _LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")

    def _get_all_md_files(self) -> list[Path]:
        return list(DOCS_DIR.rglob("*.md"))

    def test_internal_links_resolve(self) -> None:
        """All [text](file.md) links must point to existing files."""
        broken = []
        for md_file in self._get_all_md_files():
            content = md_file.read_text(encoding="utf-8")
            for match in self._LINK_RE.finditer(content):
                target = match.group(2)
                # Skip external URLs, anchors-only, and image badges
                if target.startswith(("http://", "https://", "#", "mailto:")):
                    continue
                # Strip anchor
                target_path = target.split("#")[0]
                if not target_path:
                    continue
                # Resolve relative to the file's directory
                resolved = (md_file.parent / target_path).resolve()
                if not resolved.exists():
                    broken.append(f"{md_file.name}: {target}")
        assert not broken, "Broken internal links:\n" + "\n".join(broken)


# ---------------------------------------------------------------------------
# Required content checks
# ---------------------------------------------------------------------------


class TestDocsContent:
    """Validate key content is present in documentation pages."""

    def test_index_has_quick_start(self) -> None:
        content = (DOCS_DIR / "index.md").read_text()
        assert "Quick Start" in content

    def test_index_has_feature_cards(self) -> None:
        content = (DOCS_DIR / "index.md").read_text()
        assert "feature-card" in content

    def test_installation_has_all_package_managers(self) -> None:
        """Installation page covers uv, pip, and pipx."""
        content = (DOCS_DIR / "installation.md").read_text()
        for manager in ("uv", "pip", "pipx"):
            assert manager in content, f"Installation page missing {manager}"

    def test_installation_mentions_weasyprint(self) -> None:
        content = (DOCS_DIR / "installation.md").read_text()
        assert "WeasyPrint" in content

    def test_cli_documents_all_formats(self) -> None:
        """CLI page documents all output formats."""
        content = (DOCS_DIR / "cli.md").read_text()
        for fmt in ("pdf", "docx", "html", "odt", "all"):
            assert fmt in content, f"CLI page missing format: {fmt}"

    def test_cli_documents_local_time(self) -> None:
        content = (DOCS_DIR / "cli.md").read_text()
        assert "--local-time" in content

    def test_cli_documents_watermark(self) -> None:
        content = (DOCS_DIR / "cli.md").read_text()
        assert "--watermark" in content or "watermark" in content.lower()

    def test_configuration_has_all_sections(self) -> None:
        """Configuration page covers footer, pdf, and environment variables."""
        content = (DOCS_DIR / "configuration.md").read_text()
        for section in ("footer", "pdf", "Environment variable"):
            assert section in content, f"Configuration missing section: {section}"

    def test_configuration_documents_watermark(self) -> None:
        content = (DOCS_DIR / "configuration.md").read_text()
        assert "watermark" in content.lower()

    def test_ci_covers_github_and_gitlab(self) -> None:
        """CI page covers both GitHub Actions and GitLab CI."""
        content = (DOCS_DIR / "ci.md").read_text()
        assert "GitHub Action" in content
        assert "GitLab CI" in content

    def test_ci_documents_env_vars(self) -> None:
        content = (DOCS_DIR / "ci.md").read_text()
        assert "LEAFPRESS_COMPANY_NAME" in content

    def test_changelog_has_current_version(self) -> None:
        content = (DOCS_DIR / "changelog.md").read_text()
        assert "0.1.1" in content

    def test_changelog_has_watermark(self) -> None:
        content = (DOCS_DIR / "changelog.md").read_text()
        assert "watermark" in content.lower() or "Watermark" in content

    def test_branding_page_exists_and_has_content(self) -> None:
        path = DOCS_DIR / "branding.md"
        assert path.exists()
        content = path.read_text()
        assert len(content) > 100


# ---------------------------------------------------------------------------
# MkDocs extensions consistency
# ---------------------------------------------------------------------------


class TestMkDocsExtensions:
    """Validate required markdown extensions are configured."""

    def test_has_admonition(self, mkdocs_config: dict) -> None:
        extensions = mkdocs_config.get("markdown_extensions", [])
        ext_names = [e if isinstance(e, str) else list(e.keys())[0] for e in extensions]
        assert "admonition" in ext_names

    def test_has_pymdownx_tabbed(self, mkdocs_config: dict) -> None:
        """pymdownx.tabbed is required for tab syntax in docs."""
        extensions = mkdocs_config.get("markdown_extensions", [])
        ext_names = [e if isinstance(e, str) else list(e.keys())[0] for e in extensions]
        assert "pymdownx.tabbed" in ext_names

    def test_has_pymdownx_superfences(self, mkdocs_config: dict) -> None:
        extensions = mkdocs_config.get("markdown_extensions", [])
        ext_names = [e if isinstance(e, str) else list(e.keys())[0] for e in extensions]
        assert "pymdownx.superfences" in ext_names

    def test_has_codehilite_or_highlight(self, mkdocs_config: dict) -> None:
        extensions = mkdocs_config.get("markdown_extensions", [])
        ext_names = [e if isinstance(e, str) else list(e.keys())[0] for e in extensions]
        assert "codehilite" in ext_names or "pymdownx.highlight" in ext_names


# ---------------------------------------------------------------------------
# Assets
# ---------------------------------------------------------------------------


class TestDocsAssets:
    """Validate referenced assets exist."""

    def test_extra_css_files_exist(self, mkdocs_config: dict) -> None:
        for css_path in mkdocs_config.get("extra_css", []):
            full_path = DOCS_DIR / css_path
            assert full_path.exists(), f"Missing CSS file: {css_path}"

    def test_logo_referenced_exists(self, mkdocs_config: dict) -> None:
        theme = mkdocs_config.get("theme", {})
        logo = theme.get("logo")
        if logo:
            assert (DOCS_DIR / logo).exists(), f"Logo not found: {logo}"

    def test_favicon_referenced_exists(self, mkdocs_config: dict) -> None:
        theme = mkdocs_config.get("theme", {})
        favicon = theme.get("favicon")
        if favicon:
            assert (DOCS_DIR / favicon).exists(), f"Favicon not found: {favicon}"
