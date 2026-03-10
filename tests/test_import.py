"""Tests for DOCX to Markdown import."""

from pathlib import Path

import pytest
from docx import Document as DocxDocument
from typer.testing import CliRunner

from leafpress.cli import cli
from leafpress.exceptions import DocxImportError
from leafpress.importer.converter import ImportResult, _postprocess_markdown, import_docx

runner = CliRunner()


def test_import_basic(sample_docx: Path, tmp_output: Path) -> None:
    """End-to-end: DOCX in, .md out, file exists with content."""
    result = import_docx(sample_docx, output_path=tmp_output)
    assert result.markdown_path.exists()
    assert result.markdown_path.suffix == ".md"
    content = result.markdown_path.read_text()
    assert len(content) > 0
    assert "Test Document" in content


def test_import_headings(sample_docx: Path, tmp_output: Path) -> None:
    """Headings converted to ATX-style markdown."""
    result = import_docx(sample_docx, output_path=tmp_output)
    content = result.markdown_path.read_text()
    assert "# Test Document" in content
    assert "## Section Two" in content
    assert "## Tables" in content


def test_import_formatting(sample_docx: Path, tmp_output: Path) -> None:
    """Bold and italic formatting preserved."""
    result = import_docx(sample_docx, output_path=tmp_output)
    content = result.markdown_path.read_text()
    assert "**bold text**" in content
    assert "*italic text*" in content


def test_import_lists(sample_docx: Path, tmp_output: Path) -> None:
    """Ordered and unordered lists present in output."""
    result = import_docx(sample_docx, output_path=tmp_output)
    content = result.markdown_path.read_text()
    assert "First item" in content
    assert "Second item" in content
    assert "Numbered one" in content
    assert "Numbered two" in content


def test_import_tables(sample_docx: Path, tmp_output: Path) -> None:
    """Tables converted to pipe-style markdown."""
    result = import_docx(sample_docx, output_path=tmp_output)
    content = result.markdown_path.read_text()
    assert "Header 1" in content
    assert "Header 2" in content
    assert "Cell A" in content
    assert "Cell B" in content
    # Should have pipe table separator
    assert "---" in content


def test_import_images_extracted(tmp_path: Path, tmp_output: Path) -> None:
    """Images extracted to assets/ and referenced in markdown."""
    # Create a DOCX with an image
    doc = DocxDocument()
    doc.add_heading("Image Test", level=1)
    # Create a small PNG (1x1 pixel)
    import struct
    import zlib

    def _make_png() -> bytes:
        """Create minimal 1x1 red PNG."""

        def _chunk(chunk_type: bytes, data: bytes) -> bytes:
            c = chunk_type + data
            return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

        sig = b"\x89PNG\r\n\x1a\n"
        ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        raw = zlib.compress(b"\x00\xff\x00\x00")
        idat = _chunk(b"IDAT", raw)
        iend = _chunk(b"IEND", b"")
        return sig + ihdr + idat + iend

    img_path = tmp_path / "test.png"
    img_path.write_bytes(_make_png())
    doc.add_picture(str(img_path))
    docx_path = tmp_path / "with_image.docx"
    doc.save(str(docx_path))

    result = import_docx(docx_path, output_path=tmp_output)
    assert len(result.images) >= 1
    assert result.images[0].exists()
    content = result.markdown_path.read_text()
    assert "assets/" in content


def test_import_no_images_flag(tmp_path: Path, tmp_output: Path) -> None:
    """--no-extract-images skips image extraction."""
    doc = DocxDocument()
    doc.add_heading("No Images", level=1)
    docx_path = tmp_path / "no_images.docx"
    doc.save(str(docx_path))

    result = import_docx(docx_path, output_path=tmp_output, extract_images=False)
    assert result.images == []
    assets_dir = tmp_output / "assets"
    assert not assets_dir.exists()


def test_import_output_dir(sample_docx: Path, tmp_output: Path) -> None:
    """-o dir/ creates dir/stem.md."""
    result = import_docx(sample_docx, output_path=tmp_output)
    assert result.markdown_path == tmp_output / "test.md"
    assert result.markdown_path.exists()


def test_import_output_file(sample_docx: Path, tmp_output: Path) -> None:
    """-o file.md writes to exact path."""
    out_file = tmp_output / "custom.md"
    result = import_docx(sample_docx, output_path=out_file)
    assert result.markdown_path == out_file
    assert out_file.exists()


def test_import_default_output(sample_docx: Path) -> None:
    """No -o writes sibling .md next to the docx."""
    result = import_docx(sample_docx, output_path=None)
    expected = sample_docx.with_suffix(".md")
    assert result.markdown_path == expected
    assert expected.exists()


def test_import_nonexistent_file(tmp_path: Path) -> None:
    """Raises DocxImportError for missing file."""
    with pytest.raises(DocxImportError, match="File not found"):
        import_docx(tmp_path / "nonexistent.docx")


def test_import_non_docx_file(tmp_path: Path) -> None:
    """Raises DocxImportError for non-.docx file."""
    txt_file = tmp_path / "readme.txt"
    txt_file.write_text("hello")
    with pytest.raises(DocxImportError, match=r"Not a \.docx file"):
        import_docx(txt_file)


def test_import_cli(sample_docx: Path, tmp_output: Path) -> None:
    """CLI end-to-end test."""
    result = runner.invoke(cli, ["import", str(sample_docx), "-o", str(tmp_output)])
    assert result.exit_code == 0
    assert "Done!" in result.output
    assert (tmp_output / "test.md").exists()


def test_import_cli_nonexistent(tmp_path: Path) -> None:
    """CLI exits 1 for missing file."""
    result = runner.invoke(cli, ["import", str(tmp_path / "missing.docx")])
    assert result.exit_code == 1
    assert "Error" in result.output


def test_postprocess_markdown() -> None:
    """Blank lines collapsed, trailing whitespace stripped."""
    raw = "# Title\n\n\n\nParagraph   \n\n\n\n\nEnd  "
    cleaned = _postprocess_markdown(raw)
    assert "\n\n\n" not in cleaned
    assert "   \n" not in cleaned
    assert cleaned.endswith("\n")
    assert not cleaned.endswith("\n\n")


def test_import_result_dataclass() -> None:
    """ImportResult holds expected fields."""
    r = ImportResult(markdown_path=Path("test.md"))
    assert r.markdown_path == Path("test.md")
    assert r.images == []
    assert r.warnings == []


# --- Direct markdown converter unit tests ---

from leafpress.importer.markdown_converter import LeafpressMarkdownConverter  # noqa: E402


def _convert_html(html: str) -> str:
    """Helper to convert HTML snippet through the converter."""
    return LeafpressMarkdownConverter(strip=["html", "body"]).convert(html).strip()


def test_converter_fenced_code_block() -> None:
    """<pre><code> converts to fenced code block."""
    html = "<pre><code>print('hello')</code></pre>"
    md = _convert_html(html)
    assert "```" in md
    assert "print('hello')" in md


def test_converter_fenced_code_with_language() -> None:
    """<pre><code class='language-python'> gets language annotation."""
    html = '<pre><code class="language-python">x = 1</code></pre>'
    md = _convert_html(html)
    assert "```python" in md
    assert "x = 1" in md


def test_converter_fenced_code_no_language() -> None:
    """<pre><code> without language class produces bare fence."""
    html = "<pre><code>some code</code></pre>"
    md = _convert_html(html)
    assert "```\n" in md
    assert "some code" in md


def test_converter_fenced_code_non_language_class() -> None:
    """<pre><code class='highlight'> (not language-*) produces bare fence."""
    html = '<pre><code class="highlight">foo</code></pre>'
    md = _convert_html(html)
    assert "```\n" in md or md.startswith("```\n") or "```\nfoo" in md


def test_converter_pipe_table() -> None:
    """<table> converts to pipe-style markdown table."""
    html = (
        "<table>"
        "<tr><th>A</th><th>B</th></tr>"
        "<tr><td>1</td><td>2</td></tr>"
        "</table>"
    )
    md = _convert_html(html)
    assert "| A" in md
    assert "| B" in md
    assert "---" in md
    assert "| 1" in md
    assert "| 2" in md


def test_converter_table_uneven_rows() -> None:
    """Table with uneven row lengths pads shorter rows."""
    html = (
        "<table>"
        "<tr><th>A</th><th>B</th><th>C</th></tr>"
        "<tr><td>1</td><td>2</td></tr>"
        "</table>"
    )
    md = _convert_html(html)
    # Should still produce a valid table with 3 columns
    lines = [line for line in md.split("\n") if line.startswith("|")]
    assert len(lines) == 3  # header + separator + data row
    # Each line should have 3 pipe-separated cells
    for line in lines:
        assert line.count("|") >= 4  # | cell | cell | cell |


def test_converter_table_empty() -> None:
    """<table> with no rows falls through gracefully."""
    html = "<table></table>"
    md = _convert_html(html)
    # Should not crash; result is whatever fallback markdownify gives
    assert isinstance(md, str)
