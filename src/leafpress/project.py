"""Auto-detect the MkDocs project directory from the current working directory."""

from __future__ import annotations

import logging
from pathlib import Path

from leafpress.exceptions import SourceError
from leafpress.mkdocs_parser import find_site_config

logger = logging.getLogger(__name__)


def detect_project(cwd: Path | None = None) -> Path:
    """Auto-detect the MkDocs project directory.

    Search order:
    1. Git repo root (if in a git repo)
    2. Git root / "docs/"
    3. CWD
    4. CWD / "docs/"

    Returns:
        The directory containing mkdocs.yml/mkdocs.yaml (or zensical.toml).

    Raises:
        SourceError: If no site config can be found.
    """
    cwd = (cwd or Path.cwd()).resolve()

    search_roots: list[Path] = []

    git_root = _find_git_root(cwd)
    if git_root is not None:
        search_roots.append(git_root)
        docs_subdir = git_root / "docs"
        if docs_subdir.is_dir():
            search_roots.append(docs_subdir)

    # Add CWD and CWD/docs if not already covered by git root
    if cwd not in search_roots:
        search_roots.append(cwd)
    cwd_docs = cwd / "docs"
    if cwd_docs.is_dir() and cwd_docs not in search_roots:
        search_roots.append(cwd_docs)

    result = _find_mkdocs_dir(search_roots)
    if result is not None:
        logger.info("Detected project: %s", result)
        return result

    searched = ", ".join(str(p) for p in search_roots)
    raise SourceError(
        f"No mkdocs.yml or zensical.toml found. Searched: {searched}\n"
        "Specify a source path: leafpress convert /path/to/project"
    )


def _find_git_root(cwd: Path) -> Path | None:
    """Find the git repo root from *cwd*, or ``None`` if not in a repo."""
    try:
        from git import InvalidGitRepositoryError, Repo

        repo = Repo(str(cwd), search_parent_directories=True)
        return Path(repo.working_dir)
    except InvalidGitRepositoryError:
        return None
    except Exception:
        # GitPython can raise various errors for bare repos, etc.
        return None


def _find_mkdocs_dir(search_roots: list[Path]) -> Path | None:
    """Return the first directory in *search_roots* that contains an mkdocs config."""
    for root in search_roots:
        if find_site_config(root) is not None:
            return root
    return None
