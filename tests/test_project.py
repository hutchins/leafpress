"""Tests for project auto-detection."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from git import Repo

from leafpress.exceptions import SourceError
from leafpress.project import _find_git_root, _find_mkdocs_dir, detect_project


# --- _find_git_root ---


def test_find_git_root_in_repo(tmp_path: Path) -> None:
    """Returns the repo root when CWD is in a git repo."""
    Repo.init(str(tmp_path))
    assert _find_git_root(tmp_path) == tmp_path


def test_find_git_root_from_subdirectory(tmp_path: Path) -> None:
    """Returns the repo root when CWD is a subdirectory of a git repo."""
    Repo.init(str(tmp_path))
    subdir = tmp_path / "a" / "b"
    subdir.mkdir(parents=True)
    assert _find_git_root(subdir) == tmp_path


def test_find_git_root_returns_none_outside_repo(tmp_path: Path) -> None:
    """Returns None when CWD is not in a git repo."""
    assert _find_git_root(tmp_path) is None


# --- _find_mkdocs_dir ---


def test_find_mkdocs_dir_yml(tmp_path: Path) -> None:
    """Finds a directory containing mkdocs.yml."""
    (tmp_path / "mkdocs.yml").write_text("site_name: test")
    assert _find_mkdocs_dir([tmp_path]) == tmp_path


def test_find_mkdocs_dir_yaml(tmp_path: Path) -> None:
    """Finds a directory containing mkdocs.yaml."""
    (tmp_path / "mkdocs.yaml").write_text("site_name: test")
    assert _find_mkdocs_dir([tmp_path]) == tmp_path


def test_find_mkdocs_dir_prefers_first_root(tmp_path: Path) -> None:
    """Returns the first matching root when multiple contain mkdocs.yml."""
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    dir_a.mkdir()
    dir_b.mkdir()
    (dir_a / "mkdocs.yml").write_text("site_name: a")
    (dir_b / "mkdocs.yml").write_text("site_name: b")
    assert _find_mkdocs_dir([dir_a, dir_b]) == dir_a


def test_find_mkdocs_dir_returns_none_when_empty(tmp_path: Path) -> None:
    """Returns None when no root contains mkdocs.yml."""
    assert _find_mkdocs_dir([tmp_path]) is None


def test_find_mkdocs_dir_skips_directories_named_mkdocs(tmp_path: Path) -> None:
    """Ignores directories named mkdocs.yml (only matches files)."""
    (tmp_path / "mkdocs.yml").mkdir()
    assert _find_mkdocs_dir([tmp_path]) is None


# --- detect_project ---


def test_detect_in_git_root(tmp_path: Path) -> None:
    """Detects mkdocs.yml at the git repo root."""
    Repo.init(str(tmp_path))
    (tmp_path / "mkdocs.yml").write_text("site_name: test")
    result = detect_project(cwd=tmp_path)
    assert result == tmp_path


def test_detect_in_git_docs_subdir(tmp_path: Path) -> None:
    """Detects mkdocs.yml in docs/ under the git root."""
    Repo.init(str(tmp_path))
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "mkdocs.yml").write_text("site_name: test")
    result = detect_project(cwd=tmp_path)
    assert result == docs


def test_detect_from_subdirectory_of_git_repo(tmp_path: Path) -> None:
    """Detects project when CWD is a subdirectory of the git repo."""
    Repo.init(str(tmp_path))
    (tmp_path / "mkdocs.yml").write_text("site_name: test")
    subdir = tmp_path / "src" / "app"
    subdir.mkdir(parents=True)
    result = detect_project(cwd=subdir)
    assert result == tmp_path


def test_detect_cwd_fallback(tmp_path: Path) -> None:
    """Falls back to CWD when not in a git repo."""
    (tmp_path / "mkdocs.yml").write_text("site_name: test")
    with patch("leafpress.project._find_git_root", return_value=None):
        result = detect_project(cwd=tmp_path)
    assert result == tmp_path


def test_detect_cwd_docs_fallback(tmp_path: Path) -> None:
    """Falls back to CWD/docs/ when not in a git repo."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "mkdocs.yml").write_text("site_name: test")
    with patch("leafpress.project._find_git_root", return_value=None):
        result = detect_project(cwd=tmp_path)
    assert result == docs


def test_detect_prefers_git_root_over_cwd_docs(tmp_path: Path) -> None:
    """Git root match takes priority over CWD/docs/."""
    Repo.init(str(tmp_path))
    (tmp_path / "mkdocs.yml").write_text("site_name: root")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "mkdocs.yml").write_text("site_name: docs")
    result = detect_project(cwd=tmp_path)
    assert result == tmp_path


def test_detect_finds_yaml_extension(tmp_path: Path) -> None:
    """Detects mkdocs.yaml (not just .yml)."""
    Repo.init(str(tmp_path))
    (tmp_path / "mkdocs.yaml").write_text("site_name: test")
    result = detect_project(cwd=tmp_path)
    assert result == tmp_path


def test_detect_raises_when_not_found(tmp_path: Path) -> None:
    """Raises SourceError when no mkdocs.yml is found anywhere."""
    with patch("leafpress.project._find_git_root", return_value=None):
        with pytest.raises(SourceError, match="No mkdocs.yml found"):
            detect_project(cwd=tmp_path)


def test_detect_raises_helpful_message(tmp_path: Path) -> None:
    """Error message suggests specifying a source path."""
    with patch("leafpress.project._find_git_root", return_value=None):
        with pytest.raises(SourceError, match="leafpress convert /path/to/project"):
            detect_project(cwd=tmp_path)


def test_detect_deduplicates_cwd_equals_git_root(tmp_path: Path) -> None:
    """When CWD is the git root, doesn't search the same directory twice."""
    Repo.init(str(tmp_path))
    (tmp_path / "mkdocs.yml").write_text("site_name: test")
    # Should work fine — no duplicate search paths
    result = detect_project(cwd=tmp_path)
    assert result == tmp_path
