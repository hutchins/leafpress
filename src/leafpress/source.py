"""Input source resolution -- git clone or local directory."""

from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path
from typing import Optional

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
    branch: Optional[str] = None,
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


def _clone_repo(url: str, branch: Optional[str]) -> Path:
    """Clone a git repo to a temporary directory."""
    tmp_dir = Path(tempfile.mkdtemp(prefix="leafpress_"))
    clone_kwargs: dict[str, object] = {"depth": 50}
    if branch:
        clone_kwargs["branch"] = branch

    try:
        console.print(f"[dim]Cloning {url}...[/dim]")
        Repo.clone_from(url, str(tmp_dir), **clone_kwargs)
    except Exception as e:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise SourceError(f"Failed to clone {url}: {e}") from e

    return tmp_dir
