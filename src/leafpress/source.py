"""Input source resolution -- git clone or local directory."""

from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path

from git import Repo
from rich.console import Console

from leafpress.exceptions import SourceError

console = Console()

GIT_URL_PATTERN = re.compile(r"^(https?://|git@|git://|ssh://)")


class ResolvedSource:
    """Context manager for a resolved source directory.

    Automatically cleans up temporary directories (cloned repos).
    """

    def __init__(self, path: Path, is_temporary: bool) -> None:
        self.path = path
        self.is_temporary = is_temporary

    def __enter__(self) -> Path:
        return self.path

    def __exit__(self, *args: object) -> None:
        if self.is_temporary:
            shutil.rmtree(self.path, ignore_errors=True)


def resolve_source(
    source: str,
    branch: str | None = None,
) -> ResolvedSource:
    """Resolve the input source to a local directory path.

    Args:
        source: A local path or git URL.
        branch: Git branch to checkout (only for git URLs).

    Returns:
        ResolvedSource context manager.
    """
    if GIT_URL_PATTERN.match(source):
        return ResolvedSource(_clone_repo(source, branch), is_temporary=True)

    local_path = Path(source).resolve()
    if not local_path.is_dir():
        raise SourceError(f"Directory not found: {local_path}")
    return ResolvedSource(local_path, is_temporary=False)


def _clone_repo(url: str, branch: str | None) -> Path:
    """Clone a git repo to a temporary directory."""
    tmp_dir = Path(tempfile.mkdtemp(prefix="leafpress_"))
    try:
        console.print(f"[dim]Cloning {url}...[/dim]")
        if branch:
            Repo.clone_from(url, str(tmp_dir), depth=50, branch=branch)
        else:
            Repo.clone_from(url, str(tmp_dir), depth=50)
    except Exception as e:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise SourceError(f"Failed to clone {url}: {e}") from e

    return tmp_dir
