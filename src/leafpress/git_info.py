"""Extract git version information from a repository."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from git import GitCommandError, GitCommandNotFound, InvalidGitRepositoryError, Repo


@dataclass(frozen=True)
class GitVersion:
    """Captured git version info for footer injection."""

    commit_hash: str
    commit_hash_full: str
    commit_date: datetime
    branch: str
    tag: str | None
    is_dirty: bool
    tag_distance: int | None

    def format_version_string(self) -> str:
        """Produce a human-readable version string.

        Examples:
            'v1.2.3 (abc1234, 2025-01-15)'
            'main@abc1234 (2025-01-15, dirty)'
        """
        date_str = self.commit_date.strftime("%Y-%m-%d")
        parts: list[str] = []

        if self.tag:
            if self.tag_distance and self.tag_distance > 0:
                parts.append(f"{self.tag}+{self.tag_distance}")
            else:
                parts.append(self.tag)
            parts.append(f"({self.commit_hash}, {date_str})")
        else:
            parts.append(f"{self.branch}@{self.commit_hash}")
            parts.append(f"({date_str})")

        if self.is_dirty:
            parts.append("[dirty]")

        return " ".join(parts)


def extract_git_info(repo_path: Path) -> GitVersion | None:
    """Extract git version info from a repository path.

    Returns None if the path is not a git repository.
    """
    try:
        repo = Repo(repo_path, search_parent_directories=True)
    except (InvalidGitRepositoryError, ValueError, TypeError):
        return None

    try:
        head = repo.head.commit
    except (ValueError, TypeError):
        # No commits yet (empty repo or orphan branch)
        return None

    if repo.head.is_detached:
        branch = "detached"
    else:
        try:
            branch = repo.active_branch.name
        except TypeError:
            branch = "unknown"

    # Find the most recent reachable tag
    tag_name: str | None = None
    tag_distance: int | None = None
    try:
        describe = repo.git.describe("--tags", "--abbrev=0")
        tag_name = describe
        tag_distance = int(repo.git.rev_list("--count", f"{describe}..HEAD"))
    except (GitCommandError, GitCommandNotFound, ValueError):
        pass

    return GitVersion(
        commit_hash=head.hexsha[:7],
        commit_hash_full=head.hexsha,
        commit_date=head.committed_datetime,
        branch=branch,
        tag=tag_name,
        is_dirty=repo.is_dirty(),
        tag_distance=tag_distance,
    )
