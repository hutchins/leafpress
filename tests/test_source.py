"""Tests for source module."""

from pathlib import Path

import pytest

from leafpress.exceptions import SourceError
from leafpress.source import resolve_source


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
