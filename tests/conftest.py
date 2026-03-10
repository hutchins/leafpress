"""Shared test fixtures."""

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_MKDOCS_DIR = FIXTURES_DIR / "sample_mkdocs_project"
SAMPLE_CONFIG_PATH = FIXTURES_DIR / "sample_config.yml"


@pytest.fixture
def sample_mkdocs_dir() -> Path:
    return SAMPLE_MKDOCS_DIR


@pytest.fixture
def sample_mkdocs_config() -> Path:
    return SAMPLE_MKDOCS_DIR / "mkdocs.yml"


@pytest.fixture
def sample_branding_config() -> Path:
    return SAMPLE_CONFIG_PATH


@pytest.fixture
def tmp_output(tmp_path: Path) -> Path:
    output = tmp_path / "output"
    output.mkdir()
    return output
