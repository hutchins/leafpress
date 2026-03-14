"""Tests for package_version module."""

from __future__ import annotations

from pathlib import Path

import pytest

from leafpress.package_version import _candidate_dirs, detect_package_version


# ---------------------------------------------------------------------------
# _candidate_dirs
# ---------------------------------------------------------------------------


def test_candidate_dirs_stops_at_git(tmp_path: Path) -> None:
    """Should stop walking at a .git directory."""
    (tmp_path / ".git").mkdir()
    sub = tmp_path / "docs" / "site"
    sub.mkdir(parents=True)
    dirs = _candidate_dirs(sub)
    assert dirs[-1] == tmp_path
    # should not go above the .git root
    assert tmp_path.parent not in dirs


def test_candidate_dirs_stops_at_svn(tmp_path: Path) -> None:
    """Should stop walking at a .svn directory."""
    (tmp_path / ".svn").mkdir()
    sub = tmp_path / "docs"
    sub.mkdir()
    dirs = _candidate_dirs(sub)
    assert dirs[-1] == tmp_path


def test_candidate_dirs_includes_start(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    dirs = _candidate_dirs(tmp_path)
    assert tmp_path in dirs


# ---------------------------------------------------------------------------
# detect_package_version — each manifest type
# ---------------------------------------------------------------------------


def test_pyproject_pep621(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "myapp"\nversion = "1.2.3"\n'
    )
    assert detect_package_version(tmp_path) == "1.2.3"


def test_pyproject_poetry(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "pyproject.toml").write_text(
        '[tool.poetry]\nname = "myapp"\nversion = "2.0.0"\n'
    )
    assert detect_package_version(tmp_path) == "2.0.0"


def test_cargo_toml(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "Cargo.toml").write_text(
        '[package]\nname = "myapp"\nversion = "0.3.1"\n'
    )
    assert detect_package_version(tmp_path) == "0.3.1"


def test_package_json(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "package.json").write_text('{"name": "myapp", "version": "3.1.0"}')
    assert detect_package_version(tmp_path) == "3.1.0"


def test_pom_xml(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "pom.xml").write_text(
        '<?xml version="1.0"?>\n'
        '<project xmlns="http://maven.apache.org/POM/4.0.0">\n'
        "  <version>4.5.6</version>\n"
        "</project>\n"
    )
    assert detect_package_version(tmp_path) == "4.5.6"


def test_composer_json(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "composer.json").write_text('{"name": "org/pkg", "version": "1.0.0"}')
    assert detect_package_version(tmp_path) == "1.0.0"


def test_pubspec_yaml(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "pubspec.yaml").write_text("name: myapp\nversion: 2.3.4\n")
    assert detect_package_version(tmp_path) == "2.3.4"


def test_csproj(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "MyApp.csproj").write_text(
        "<Project>\n  <PropertyGroup>\n    <Version>5.0.0</Version>\n"
        "  </PropertyGroup>\n</Project>\n"
    )
    assert detect_package_version(tmp_path) == "5.0.0"


def test_csproj_version_prefix(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "MyApp.csproj").write_text(
        "<Project>\n  <PropertyGroup>\n    <VersionPrefix>1.2.0</VersionPrefix>\n"
        "  </PropertyGroup>\n</Project>\n"
    )
    assert detect_package_version(tmp_path) == "1.2.0"


# ---------------------------------------------------------------------------
# detect_package_version — traversal
# ---------------------------------------------------------------------------


def test_finds_manifest_in_parent(tmp_path: Path) -> None:
    """Manifest in project root should be found when starting from docs subdir."""
    (tmp_path / ".git").mkdir()
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "myapp"\nversion = "9.9.9"\n'
    )
    docs = tmp_path / "docs"
    docs.mkdir()
    assert detect_package_version(docs) == "9.9.9"


def test_does_not_cross_vcs_boundary(tmp_path: Path) -> None:
    """Should not find a manifest above the .git root."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "outer"\nversion = "0.0.1"\n'
    )
    inner = tmp_path / "inner"
    inner.mkdir()
    (inner / ".git").mkdir()
    # No manifest inside inner — should NOT find the one above .git
    assert detect_package_version(inner) is None


def test_no_manifest_returns_none(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    assert detect_package_version(tmp_path) is None


def test_priority_pyproject_over_cargo(tmp_path: Path) -> None:
    """pyproject.toml takes priority over Cargo.toml in the same directory."""
    (tmp_path / ".git").mkdir()
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "myapp"\nversion = "1.0.0"\n'
    )
    (tmp_path / "Cargo.toml").write_text(
        '[package]\nname = "myapp"\nversion = "2.0.0"\n'
    )
    assert detect_package_version(tmp_path) == "1.0.0"
