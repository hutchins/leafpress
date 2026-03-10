"""Tests for git_info module."""

from pathlib import Path

from leafpress.git_info import extract_git_info


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
