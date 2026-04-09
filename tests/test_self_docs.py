"""Self-documentation test: convert LeafPress's own docs in every format.

Uses the project's real docs/ MkDocs site as input and verifies that
each supported output format (pdf, docx, html, odt, epub, markdown)
produces a valid, non-empty file.  Then imports back the formats we
support (docx) and checks the round-trip markdown is sensible.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from leafpress.importer.converter import import_docx
from leafpress.pipeline import convert

DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"

FORMATS = ["pdf", "docx", "html", "odt", "epub", "markdown"]

EXPECTED_SUFFIXES = {
    "pdf": ".pdf",
    "docx": ".docx",
    "html": ".html",
    "odt": ".odt",
    "epub": ".epub",
    "markdown": ".md",
}


@pytest.fixture
def docs_dir() -> Path:
    """Return the path to LeafPress's own MkDocs docs site."""
    mkdocs_yml = DOCS_DIR / "mkdocs.yml"
    if not mkdocs_yml.exists():
        pytest.skip("LeafPress docs/ directory not found")
    return DOCS_DIR


@pytest.mark.parametrize("fmt", FORMATS, ids=FORMATS)
def test_self_docs_convert(fmt: str, docs_dir: Path, tmp_output: Path) -> None:
    """Convert LeafPress's own documentation to each supported format."""
    result = convert(
        source=str(docs_dir),
        output_dir=tmp_output,
        format=fmt,
    )
    assert len(result) == 1, f"Expected 1 output file for {fmt}, got {len(result)}"
    output_file = result[0]
    assert output_file.exists(), f"Output file does not exist: {output_file}"
    assert output_file.suffix == EXPECTED_SUFFIXES[fmt], (
        f"Wrong suffix for {fmt}: {output_file.suffix}"
    )
    assert output_file.stat().st_size > 0, f"Output file is empty: {output_file}"


def test_self_docs_convert_all(docs_dir: Path, tmp_output: Path) -> None:
    """Convert LeafPress's own docs to all formats in a single call."""
    result = convert(
        source=str(docs_dir),
        output_dir=tmp_output,
        format="all",
    )
    assert len(result) == 6
    suffixes = {f.suffix for f in result}
    assert suffixes == {".pdf", ".docx", ".html", ".odt", ".epub", ".md"}
    for f in result:
        assert f.exists()
        assert f.stat().st_size > 0


# ---------------------------------------------------------------------------
# Round-trip import tests: export → import back to markdown
# ---------------------------------------------------------------------------


def test_self_docs_roundtrip_docx(docs_dir: Path, tmp_output: Path) -> None:
    """Export docs to DOCX, then import back to markdown."""
    exported = convert(
        source=str(docs_dir),
        output_dir=tmp_output,
        format="docx",
    )
    assert len(exported) == 1
    docx_path = exported[0]

    import_output = tmp_output / "imported"
    import_output.mkdir()
    result = import_docx(docx_path, output_path=import_output)

    assert result.markdown_path.exists()
    assert result.markdown_path.suffix == ".md"

    content = result.markdown_path.read_text()
    assert len(content) > 100

    # Key content from the docs should survive the round trip
    assert "LeafPress" in content
    assert "Installation" in content or "install" in content.lower()
