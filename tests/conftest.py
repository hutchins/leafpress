"""Shared test fixtures."""

from pathlib import Path

import pytest
from docx import Document as DocxDocument

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


@pytest.fixture
def sample_docx(tmp_path: Path) -> Path:
    """Create a minimal DOCX with various formatting for import tests."""
    doc = DocxDocument()
    doc.add_heading("Test Document", level=1)
    p = doc.add_paragraph()
    run_bold = p.add_run("bold text")
    run_bold.bold = True
    p.add_run(" and ")
    run_italic = p.add_run("italic text")
    run_italic.italic = True
    p.add_run(".")

    doc.add_heading("Section Two", level=2)
    doc.add_paragraph("First item", style="List Bullet")
    doc.add_paragraph("Second item", style="List Bullet")
    doc.add_paragraph("Numbered one", style="List Number")
    doc.add_paragraph("Numbered two", style="List Number")

    doc.add_heading("Tables", level=2)
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Header 1"
    table.cell(0, 1).text = "Header 2"
    table.cell(1, 0).text = "Cell A"
    table.cell(1, 1).text = "Cell B"

    path = tmp_path / "test.docx"
    doc.save(str(path))
    return path
