"""Tests for monorepo support in the conversion pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

import pytest

from leafpress.config import BrandingConfig, ProjectEntry
from leafpress.exceptions import SourceError
from leafpress.pipeline import _build_chapter_cover, _collect_monorepo_pages
from leafpress.source import ResolvedSource

# --- fixtures ---


def _make_mkdocs_project(root: Path, site_name: str, pages: dict[str, str]) -> Path:
    """Create a minimal MkDocs project with given pages."""
    root.mkdir(parents=True, exist_ok=True)
    docs = root / "docs"
    docs.mkdir(exist_ok=True)

    nav_entries = "\n".join(f'    - "{title}": {fname}' for fname, title in pages.items())
    (root / "mkdocs.yml").write_text(
        f"site_name: {site_name}\ndocs_dir: docs\nnav:\n{nav_entries}\n"
    )

    for fname, _title in pages.items():
        (docs / fname).write_text(f"# {_title}\n\nContent for {_title}.\n")

    return root


@pytest.fixture()
def monorepo(tmp_path: Path) -> Path:
    """Create a monorepo with two sub-projects."""
    _make_mkdocs_project(
        tmp_path / "services" / "api",
        "API Service",
        {"index.md": "Overview", "endpoints.md": "Endpoints"},
    )
    _make_mkdocs_project(
        tmp_path / "services" / "frontend",
        "Frontend App",
        {"index.md": "Getting Started", "components.md": "Components"},
    )
    return tmp_path


def _branding(**kwargs: Any) -> BrandingConfig:
    defaults: dict[str, Any] = {"company_name": "Test Corp", "project_name": "Platform Docs"}
    defaults.update(kwargs)
    return BrandingConfig(**defaults)


# --- _collect_monorepo_pages ---


def test_monorepo_collects_pages_from_all_projects(monorepo: Path) -> None:
    """Pages from both projects are present in combined output."""
    from rich.console import Console

    projects = [
        ProjectEntry(path="services/api"),
        ProjectEntry(path="services/frontend"),
    ]
    pages, count = _collect_monorepo_pages(
        projects,
        monorepo,
        monorepo / "mermaid",
        _branding(),
        Console(quiet=True),
    )
    assert count == 4  # 2 pages per project
    # Check that content from both projects is present
    html_content = " ".join(html for _, html in pages if html)
    assert "Overview" in html_content
    assert "Endpoints" in html_content
    assert "Getting Started" in html_content
    assert "Components" in html_content


def test_monorepo_chapter_headings_inserted(monorepo: Path) -> None:
    """Chapter heading NavItems are inserted with site_name."""
    from rich.console import Console

    projects = [
        ProjectEntry(path="services/api"),
        ProjectEntry(path="services/frontend"),
    ]
    pages, _ = _collect_monorepo_pages(
        projects,
        monorepo,
        monorepo / "mermaid",
        _branding(),
        Console(quiet=True),
    )
    headings = [item.title for item, _ in pages if item.path is None and item.title]
    assert "API Service" in headings
    assert "Frontend App" in headings


def test_monorepo_nav_levels_bumped(monorepo: Path) -> None:
    """Project content pages are at level 1+, not level 0."""
    from rich.console import Console

    projects = [ProjectEntry(path="services/api")]
    pages, _ = _collect_monorepo_pages(
        projects,
        monorepo,
        monorepo / "mermaid",
        _branding(),
        Console(quiet=True),
    )
    content_pages = [(item, html) for item, html in pages if item.path is not None]
    assert all(item.level >= 1 for item, _ in content_pages)


def test_monorepo_page_order_preserved(monorepo: Path) -> None:
    """Project A pages come before project B pages."""
    from rich.console import Console

    projects = [
        ProjectEntry(path="services/api"),
        ProjectEntry(path="services/frontend"),
    ]
    pages, _ = _collect_monorepo_pages(
        projects,
        monorepo,
        monorepo / "mermaid",
        _branding(),
        Console(quiet=True),
    )
    titles = [item.title for item, _ in pages if item.path is None and item.title]
    assert titles.index("API Service") < titles.index("Frontend App")


def test_monorepo_per_project_author(monorepo: Path) -> None:
    """Chapter meta shows per-project author override."""
    from rich.console import Console

    projects = [
        ProjectEntry(path="services/api", author="API Team"),
        ProjectEntry(path="services/frontend", author="Frontend Team"),
    ]
    pages, _ = _collect_monorepo_pages(
        projects,
        monorepo,
        monorepo / "mermaid",
        _branding(),
        Console(quiet=True),
    )
    meta_htmls = [html for _, html in pages if html and "Author:" in html]
    assert any("API Team" in h for h in meta_htmls)
    assert any("Frontend Team" in h for h in meta_htmls)


def test_monorepo_inherits_top_level_metadata(monorepo: Path) -> None:
    """Project without author override uses top-level branding author."""
    from rich.console import Console

    projects = [ProjectEntry(path="services/api")]
    branding = _branding(author="Global Author")
    pages, _ = _collect_monorepo_pages(
        projects,
        monorepo,
        monorepo / "mermaid",
        branding,
        Console(quiet=True),
    )
    meta_htmls = [html for _, html in pages if html and "Author:" in html]
    assert any("Global Author" in h for h in meta_htmls)


def test_monorepo_missing_project_dir_raises(tmp_path: Path) -> None:
    """Clear error for invalid project path."""
    from rich.console import Console

    projects = [ProjectEntry(path="nonexistent")]
    with pytest.raises(SourceError, match="not found"):
        _collect_monorepo_pages(
            projects,
            tmp_path,
            tmp_path / "mermaid",
            _branding(),
            Console(quiet=True),
        )


def test_monorepo_missing_mkdocs_raises(tmp_path: Path) -> None:
    """Clear error when project dir exists but has no mkdocs.yml."""
    from rich.console import Console

    (tmp_path / "empty_project").mkdir()
    projects = [ProjectEntry(path="empty_project")]
    with pytest.raises(Exception, match="mkdocs"):
        _collect_monorepo_pages(
            projects,
            tmp_path,
            tmp_path / "mermaid",
            _branding(),
            Console(quiet=True),
        )


# --- _build_chapter_cover ---


def test_build_chapter_cover_per_project_author() -> None:
    """Per-project author overrides top-level."""
    entry = ProjectEntry(path="x", author="Project Author")
    branding = _branding(author="Global Author")
    html = _build_chapter_cover(entry, branding, "My Chapter", "x")
    assert "Project Author" in html
    assert "Global Author" not in html


def test_build_chapter_cover_inherits_branding() -> None:
    """Falls back to top-level branding when no per-project override."""
    entry = ProjectEntry(path="x")
    branding = _branding(author="Global Author", document_owner="Global Owner")
    html = _build_chapter_cover(entry, branding, "My Chapter", "x")
    assert "Global Author" in html
    assert "Global Owner" in html


def test_build_chapter_cover_minimal_when_no_metadata() -> None:
    """Contains title and source but no author/owner fields when absent."""
    entry = ProjectEntry(path="x")
    branding = _branding()
    html = _build_chapter_cover(entry, branding, "My Chapter", "x")
    assert "My Chapter" in html
    assert "Author" not in html
    assert "Document Owner" not in html


def test_build_chapter_cover_all_fields() -> None:
    """All metadata fields are rendered."""
    entry = ProjectEntry(
        path="x",
        author="Alice",
        author_email="alice@corp.com",
        document_owner="Bob",
        review_cycle="Quarterly",
        subtitle="Internal API",
    )
    branding = _branding()
    html = _build_chapter_cover(entry, branding, "Service Docs", "services/api")
    assert "Alice" in html
    assert "alice@corp.com" in html
    assert "Bob" in html
    assert "Quarterly" in html
    assert "Internal API" in html
    assert "Service Docs" in html
    assert "services/api" in html


def test_build_chapter_cover_has_structured_html() -> None:
    """Cover page uses structured CSS classes, not raw <p><em> tags."""
    entry = ProjectEntry(path="x", author="Alice")
    branding = _branding()
    html = _build_chapter_cover(entry, branding, "My Chapter", "x")
    assert "chapter-cover" in html
    assert "chapter-title" in html
    assert "chapter-meta" in html


# --- config tests ---


def test_normalize_projects_strings() -> None:
    """Simple string paths are normalized to ProjectEntry."""
    config = BrandingConfig(
        company_name="Test",
        project_name="Docs",
        projects=cast(Any, ["services/api", "services/frontend"]),
    )
    assert len(config.projects) == 2
    assert config.projects[0].path == "services/api"
    assert config.projects[1].path == "services/frontend"


def test_normalize_projects_dicts() -> None:
    """Detailed dict entries are accepted."""
    config = BrandingConfig(
        company_name="Test",
        project_name="Docs",
        projects=cast(Any, [{"path": "svc/api", "author": "API Team"}]),
    )
    assert config.projects[0].path == "svc/api"
    assert config.projects[0].author == "API Team"


def test_normalize_projects_mixed() -> None:
    """Mix of strings and dicts works."""
    config = BrandingConfig(
        company_name="Test",
        project_name="Docs",
        projects=cast(Any, ["simple/path", {"path": "detailed/path", "author": "Team"}]),
    )
    assert config.projects[0].path == "simple/path"
    assert config.projects[0].author is None
    assert config.projects[1].path == "detailed/path"
    assert config.projects[1].author == "Team"


# --- git URL project tests ---


def test_project_entry_url_valid() -> None:
    """ProjectEntry accepts url instead of path."""
    entry = ProjectEntry(url="https://github.com/org/repo", author="Remote Team")
    assert entry.url == "https://github.com/org/repo"
    assert entry.path is None
    assert entry.author == "Remote Team"


def test_project_entry_url_with_branch() -> None:
    """ProjectEntry accepts url + branch."""
    entry = ProjectEntry(url="https://github.com/org/repo", branch="develop")
    assert entry.branch == "develop"


def test_project_entry_no_path_or_url_raises() -> None:
    """ProjectEntry with neither path nor url is invalid."""
    with pytest.raises(ValueError, match="either 'path' or 'url'"):
        ProjectEntry()


def test_project_entry_both_path_and_url_raises() -> None:
    """ProjectEntry with both path and url is invalid."""
    with pytest.raises(ValueError, match="cannot have both"):
        ProjectEntry(path="local/dir", url="https://github.com/org/repo")


def test_monorepo_url_project_cloned(monorepo: Path) -> None:
    """Git URL project is cloned and pages collected."""
    from rich.console import Console

    # Use the existing api fixture as a "remote" project
    api_dir = monorepo / "services" / "api"

    projects = [
        ProjectEntry(url="https://github.com/org/api-docs"),
    ]

    def mock_resolve(url, branch=None):
        return ResolvedSource(api_dir, is_temporary=False)

    with patch("leafpress.pipeline.resolve_source", side_effect=mock_resolve):
        pages, count = _collect_monorepo_pages(
            projects,
            monorepo,
            monorepo / "mermaid",
            _branding(),
            Console(quiet=True),
        )

    assert count == 2  # api project has 2 pages
    headings = [item.title for item, _ in pages if item.path is None and item.title]
    assert "API Service" in headings


def test_monorepo_mixed_path_and_url(monorepo: Path) -> None:
    """Mix of local path and git URL projects works."""
    from rich.console import Console

    frontend_dir = monorepo / "services" / "frontend"

    projects = [
        ProjectEntry(path="services/api"),
        ProjectEntry(url="https://github.com/org/frontend-docs"),
    ]

    def mock_resolve(url, branch=None):
        return ResolvedSource(frontend_dir, is_temporary=False)

    with patch("leafpress.pipeline.resolve_source", side_effect=mock_resolve):
        pages, count = _collect_monorepo_pages(
            projects,
            monorepo,
            monorepo / "mermaid",
            _branding(),
            Console(quiet=True),
        )

    assert count == 4  # 2 from local api + 2 from "remote" frontend
    headings = [item.title for item, _ in pages if item.path is None and item.title]
    assert "API Service" in headings
    assert "Frontend App" in headings


def test_monorepo_url_passes_branch(monorepo: Path) -> None:
    """Branch is passed through to resolve_source for URL projects."""
    from rich.console import Console

    api_dir = monorepo / "services" / "api"

    projects = [
        ProjectEntry(url="https://github.com/org/repo", branch="develop"),
    ]

    captured_args: list[tuple] = []

    def mock_resolve(url, branch=None):
        captured_args.append((url, branch))
        return ResolvedSource(api_dir, is_temporary=False)

    with patch("leafpress.pipeline.resolve_source", side_effect=mock_resolve):
        _collect_monorepo_pages(
            projects,
            monorepo,
            monorepo / "mermaid",
            _branding(),
            Console(quiet=True),
        )

    assert captured_args[0] == ("https://github.com/org/repo", "develop")


# --- root field tests ---


def test_project_entry_accepts_root() -> None:
    """ProjectEntry accepts the root field."""
    entry = ProjectEntry(path="services/api/docs", root="services/api")
    assert entry.root == "services/api"
    assert entry.path == "services/api/docs"


def test_project_entry_root_defaults_to_none() -> None:
    """root is None when not specified."""
    entry = ProjectEntry(path="services/api")
    assert entry.root is None


def test_monorepo_root_used_for_version_detection(monorepo: Path) -> None:
    """When root is set, version detection uses root dir instead of path dir."""
    from rich.console import Console

    # Create a project where mkdocs.yml is in a docs/ subdirectory
    api_root = monorepo / "services" / "api"
    docs_dir = api_root / "docs"
    _make_mkdocs_project(docs_dir, "API Service", {"index.md": "Overview"})

    # Put a pyproject.toml with a version in the api root (not in docs/)
    (api_root / "pyproject.toml").write_text('[project]\nname = "api"\nversion = "2.5.0"\n')

    projects = [
        ProjectEntry(path="services/api/docs", root="services/api"),
    ]

    pages, _count = _collect_monorepo_pages(
        projects,
        monorepo,
        monorepo / "mermaid",
        _branding(),
        Console(quiet=True),
    )

    # The chapter cover should contain the version from root's pyproject.toml
    cover_html = [html for _, html in pages if html and "chapter-cover" in html]
    assert len(cover_html) == 1
    assert "2.5.0" in cover_html[0]


def test_monorepo_no_root_uses_path_for_version(monorepo: Path) -> None:
    """When root is not set, version detection uses the path dir (default)."""
    from rich.console import Console

    # The standard monorepo fixture has mkdocs.yml at services/api/
    # Put a pyproject.toml there so version is found via path
    api_dir = monorepo / "services" / "api"
    (api_dir / "pyproject.toml").write_text('[project]\nname = "api"\nversion = "1.0.0"\n')

    projects = [
        ProjectEntry(path="services/api"),  # no root set
    ]

    pages, _count = _collect_monorepo_pages(
        projects,
        monorepo,
        monorepo / "mermaid",
        _branding(),
        Console(quiet=True),
    )

    cover_html = [html for _, html in pages if html and "chapter-cover" in html]
    assert len(cover_html) == 1
    assert "1.0.0" in cover_html[0]
