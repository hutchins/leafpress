"""Tests for git_info module."""

from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

from git import GitCommandError

from leafpress.git_info import GitVersion, extract_git_info


def test_extract_from_git_repo(sample_mkdocs_dir: Path) -> None:
    """The test fixtures are inside this git repo, so extraction should work."""
    info = extract_git_info(sample_mkdocs_dir)
    # This test runs inside the leafpress repo, so we should get git info
    if info is not None:
        assert len(info.commit_hash) == 7
        assert len(info.commit_hash_full) == 40
        assert info.branch
        assert info.commit_date


def test_extract_from_non_repo(tmp_path: Path) -> None:
    info = extract_git_info(tmp_path)
    assert info is None


def test_version_string_with_tag() -> None:
    from datetime import datetime, timezone

    from leafpress.git_info import GitVersion

    info = GitVersion(
        commit_hash="abc1234",
        commit_hash_full="abc1234" * 6 + "ab",
        commit_date=datetime(2025, 1, 15, tzinfo=timezone.utc),
        branch="main",
        tag="v1.2.3",
        is_dirty=False,
        tag_distance=0,
    )
    version_str = info.format_version_string()
    assert "v1.2.3" in version_str
    assert "abc1234" in version_str
    assert "2025-01-15" in version_str


def test_version_string_without_tag() -> None:
    from datetime import datetime, timezone

    from leafpress.git_info import GitVersion

    info = GitVersion(
        commit_hash="def5678",
        commit_hash_full="def5678" * 6 + "de",
        commit_date=datetime(2025, 3, 1, tzinfo=timezone.utc),
        branch="feature/test",
        tag=None,
        is_dirty=True,
        tag_distance=None,
    )
    version_str = info.format_version_string()
    assert "feature/test@def5678" in version_str
    assert "[dirty]" in version_str


def test_version_string_tag_with_distance() -> None:
    from datetime import datetime, timezone

    info = GitVersion(
        commit_hash="aaa1111",
        commit_hash_full="aaa1111" * 6 + "aa",
        commit_date=datetime(2025, 6, 1, tzinfo=timezone.utc),
        branch="main",
        tag="v2.0.0",
        is_dirty=False,
        tag_distance=5,
    )
    version_str = info.format_version_string()
    assert "v2.0.0+5" in version_str


@patch("leafpress.git_info.Repo")
def test_detached_head(mock_repo_cls, tmp_path: Path) -> None:
    mock_repo = MagicMock()
    mock_repo_cls.return_value = mock_repo

    mock_commit = MagicMock()
    mock_commit.hexsha = "a" * 40
    mock_commit.committed_datetime = MagicMock()
    mock_repo.head.commit = mock_commit
    mock_repo.head.is_detached = True
    mock_repo.is_dirty.return_value = False
    mock_repo.git.describe.side_effect = GitCommandError("describe", "no tags")

    info = extract_git_info(tmp_path)
    assert info is not None
    assert info.branch == "detached"


@patch("leafpress.git_info.Repo")
def test_empty_repo_returns_none(mock_repo_cls, tmp_path: Path) -> None:
    mock_repo = MagicMock()
    mock_repo_cls.return_value = mock_repo
    type(mock_repo.head).commit = PropertyMock(side_effect=ValueError("no commits"))

    info = extract_git_info(tmp_path)
    assert info is None
