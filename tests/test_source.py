"""Tests for source module."""

from pathlib import Path
from unittest.mock import patch

import pytest

from leafpress.exceptions import SourceError
from leafpress.source import GIT_URL_PATTERN, ResolvedSource, _clone_repo, resolve_source


def test_resolve_local_directory(sample_mkdocs_dir: Path) -> None:
    resolved = resolve_source(str(sample_mkdocs_dir))
    with resolved as path:
        assert path.is_dir()
        assert not resolved.is_temporary


def test_resolve_nonexistent_directory() -> None:
    with pytest.raises(SourceError, match="Directory not found"):
        resolve_source("/nonexistent/path/to/nowhere")


def test_context_manager_cleanup(sample_mkdocs_dir: Path) -> None:
    resolved = resolve_source(str(sample_mkdocs_dir))
    with resolved as path:
        assert path.exists()
    # Local dirs should not be deleted
    assert sample_mkdocs_dir.exists()


class TestGitUrlPattern:
    """Test the git URL regex detection."""

    @pytest.mark.parametrize(
        "url",
        [
            "https://github.com/org/repo",
            "https://github.com/org/repo.git",
            "http://gitlab.com/org/repo",
            "git@github.com:org/repo.git",
            "git://github.com/org/repo",
            "ssh://git@github.com/org/repo",
        ],
    )
    def test_matches_git_urls(self, url: str) -> None:
        assert GIT_URL_PATTERN.match(url)

    @pytest.mark.parametrize(
        "path",
        [
            "/home/user/project",
            "./relative/path",
            "relative/path",
            "C:\\Windows\\path",
        ],
    )
    def test_rejects_local_paths(self, path: str) -> None:
        assert not GIT_URL_PATTERN.match(path)


class TestResolvedSource:
    """Test the context manager behavior."""

    def test_temporary_dir_cleaned_up(self, tmp_path: Path) -> None:
        temp_dir = tmp_path / "temp_clone"
        temp_dir.mkdir()
        resolved = ResolvedSource(temp_dir, is_temporary=True)
        with resolved as path:
            assert path.exists()
        assert not temp_dir.exists()

    def test_permanent_dir_not_cleaned(self, tmp_path: Path) -> None:
        resolved = ResolvedSource(tmp_path, is_temporary=False)
        with resolved as path:
            assert path == tmp_path
        assert tmp_path.exists()


class TestCloneRepo:
    """Test git cloning with mocked Repo."""

    @patch("leafpress.source.Repo")
    def test_clone_success(self, mock_repo, tmp_path: Path) -> None:
        with patch("leafpress.source.tempfile.mkdtemp", return_value=str(tmp_path)):
            result = _clone_repo("https://github.com/org/repo", None)
        mock_repo.clone_from.assert_called_once()
        assert result == tmp_path

    @patch("leafpress.source.Repo")
    def test_clone_with_branch(self, mock_repo, tmp_path: Path) -> None:
        with patch("leafpress.source.tempfile.mkdtemp", return_value=str(tmp_path)):
            _clone_repo("https://github.com/org/repo", "develop")
        call_kwargs = mock_repo.clone_from.call_args[1]
        assert call_kwargs["branch"] == "develop"

    @patch("leafpress.source.Repo")
    def test_clone_failure_cleans_up(self, mock_repo, tmp_path: Path) -> None:
        mock_repo.clone_from.side_effect = Exception("network error")
        temp_dir = tmp_path / "clone_dir"
        temp_dir.mkdir()
        with patch("leafpress.source.tempfile.mkdtemp", return_value=str(temp_dir)):
            with pytest.raises(SourceError, match="Failed to clone"):
                _clone_repo("https://github.com/org/repo", None)
        assert not temp_dir.exists()


class TestResolveSourceGit:
    """Test resolve_source with git URLs (mocked)."""

    @patch("leafpress.source._clone_repo")
    def test_git_url_triggers_clone(self, mock_clone, tmp_path: Path) -> None:
        mock_clone.return_value = tmp_path
        resolved = resolve_source("https://github.com/org/repo", branch="main")
        assert resolved.is_temporary
        mock_clone.assert_called_once_with("https://github.com/org/repo", "main")
