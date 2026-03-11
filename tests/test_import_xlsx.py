"""Tests for XLSX to Markdown import converter."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest
from openpyxl import Workbook

from leafpress.exceptions import XlsxImportError
from leafpress.importer.converter_xlsx import import_xlsx

# --- helpers ---


def _make_xlsx(tmp_path: Path, sheets: dict[str, list[list]]) -> Path:
    """Create an XLSX file from sheet definitions.

    Args:
        sheets: Mapping of sheet name → list of rows (each row a list of cell values).
    """
    wb = Workbook()
    # Remove the default sheet
    wb.remove(wb.active)

    for name, rows in sheets.items():
        ws = wb.create_sheet(title=name)
        for row in rows:
            ws.append(row)

    path = tmp_path / "test.xlsx"
    wb.save(path)
    return path


# --- import_xlsx tests ---


def test_import_xlsx_basic(tmp_path: Path) -> None:
    """Single sheet with header + data rows produces a Markdown table."""
    xlsx_path = _make_xlsx(
        tmp_path,
        {
            "Data": [
                ["Name", "Value"],
                ["Alpha", 100],
                ["Beta", 200],
            ],
        },
    )
    result = import_xlsx(xlsx_path)
    md = result.markdown_path.read_text()
    assert "## Data" in md
    assert "| Name" in md
    assert "| Alpha" in md
    assert "| Beta" in md
    assert "---" in md  # separator row
    assert "100" in md
    assert "200" in md


def test_import_xlsx_multiple_sheets(tmp_path: Path) -> None:
    """Each sheet gets its own ## heading and table."""
    xlsx_path = _make_xlsx(
        tmp_path,
        {
            "Users": [
                ["Name", "Email"],
                ["Alice", "alice@example.com"],
            ],
            "Products": [
                ["SKU", "Price"],
                ["A001", 9.99],
            ],
        },
    )
    result = import_xlsx(xlsx_path)
    md = result.markdown_path.read_text()
    assert "## Users" in md
    assert "## Products" in md
    assert "Alice" in md
    assert "A001" in md


def test_import_xlsx_empty_sheet_skipped(tmp_path: Path) -> None:
    """Empty worksheets are not included in output."""
    xlsx_path = _make_xlsx(
        tmp_path,
        {
            "HasData": [["Col1"], ["Val1"]],
            "Empty": [],
        },
    )
    result = import_xlsx(xlsx_path)
    md = result.markdown_path.read_text()
    assert "## HasData" in md
    assert "Empty" not in md


def test_import_xlsx_empty_cells(tmp_path: Path) -> None:
    """Blank cells render as empty table cells."""
    xlsx_path = _make_xlsx(
        tmp_path,
        {
            "Sparse": [
                ["A", "B", "C"],
                [1, None, 3],
                [None, 2, None],
            ],
        },
    )
    result = import_xlsx(xlsx_path)
    md = result.markdown_path.read_text()
    assert "## Sparse" in md
    # The table should still have proper pipe structure
    lines = [line for line in md.split("\n") if line.startswith("|")]
    assert len(lines) == 4  # header + separator + 2 data rows


def test_import_xlsx_numeric_and_date_values(tmp_path: Path) -> None:
    """Numbers and dates render as strings."""
    xlsx_path = _make_xlsx(
        tmp_path,
        {
            "Types": [
                ["Type", "Value"],
                ["Integer", 42],
                ["Float", 3.14],
                ["Date", date(2025, 6, 15)],
                ["DateTime", datetime(2025, 6, 15, 10, 30, 0)],
            ],
        },
    )
    result = import_xlsx(xlsx_path)
    md = result.markdown_path.read_text()
    assert "42" in md
    assert "3.14" in md
    assert "2025-06-15" in md
    assert "10:30:00" in md


def test_import_xlsx_pipe_in_cell_escaped(tmp_path: Path) -> None:
    """Pipe characters in cell values are escaped."""
    xlsx_path = _make_xlsx(
        tmp_path,
        {
            "Pipes": [
                ["Command", "Description"],
                ["a | b", "pipe example"],
            ],
        },
    )
    result = import_xlsx(xlsx_path)
    md = result.markdown_path.read_text()
    assert "a \\| b" in md


def test_import_xlsx_output_path_default(tmp_path: Path) -> None:
    """Default output uses same stem as input."""
    xlsx_path = _make_xlsx(tmp_path, {"Sheet1": [["A"], [1]]})
    result = import_xlsx(xlsx_path)
    assert result.markdown_path == tmp_path / "test.md"


def test_import_xlsx_output_path_directory(tmp_path: Path) -> None:
    """Directory output creates <stem>.md inside it."""
    xlsx_path = _make_xlsx(tmp_path, {"Sheet1": [["A"], [1]]})
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = import_xlsx(xlsx_path, output_path=out_dir)
    assert result.markdown_path == out_dir / "test.md"


def test_import_xlsx_output_path_explicit(tmp_path: Path) -> None:
    """Explicit output path is respected."""
    xlsx_path = _make_xlsx(tmp_path, {"Sheet1": [["A"], [1]]})
    out = tmp_path / "custom" / "output.md"
    result = import_xlsx(xlsx_path, output_path=out)
    assert result.markdown_path == out
    assert out.exists()


def test_import_xlsx_missing_file(tmp_path: Path) -> None:
    """Nonexistent file raises XlsxImportError."""
    with pytest.raises(XlsxImportError, match="File not found"):
        import_xlsx(tmp_path / "nonexistent.xlsx")


def test_import_xlsx_wrong_extension(tmp_path: Path) -> None:
    """Wrong extension raises XlsxImportError."""
    txt_file = tmp_path / "data.csv"
    txt_file.write_text("a,b\n1,2\n")
    with pytest.raises(XlsxImportError, match=r"Not a \.xlsx file"):
        import_xlsx(txt_file)


def test_import_xlsx_no_images(tmp_path: Path) -> None:
    """XLSX import never produces images."""
    xlsx_path = _make_xlsx(tmp_path, {"Sheet1": [["A"], [1]]})
    result = import_xlsx(xlsx_path)
    assert result.images == []


def test_import_xlsx_integer_floats(tmp_path: Path) -> None:
    """Whole-number floats display without decimal point."""
    xlsx_path = _make_xlsx(
        tmp_path,
        {"Numbers": [["Val"], [1.0], [42.0], [3.5]]},
    )
    result = import_xlsx(xlsx_path)
    md = result.markdown_path.read_text()
    # 1.0 and 42.0 should display as "1" and "42"
    assert "| 1 " in md or "| 1  " in md
    assert "| 42" in md
    assert "3.5" in md


# --- CLI integration ---


def test_cli_xlsx_integration(tmp_path: Path) -> None:
    """End-to-end CLI import of an XLSX file."""
    from typer.testing import CliRunner

    from leafpress.cli import cli

    xlsx_path = _make_xlsx(
        tmp_path,
        {"Report": [["Metric", "Value"], ["Revenue", 1000]]},
    )
    runner = CliRunner()
    result = runner.invoke(
        cli, ["import", str(xlsx_path), "-o", str(tmp_path / "out.md")]
    )
    assert result.exit_code == 0
    assert "Done!" in result.output
    assert (tmp_path / "out.md").exists()
    md = (tmp_path / "out.md").read_text()
    assert "## Report" in md
    assert "Revenue" in md
