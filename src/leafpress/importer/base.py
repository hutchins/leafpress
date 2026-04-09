"""Shared utilities for all import converters."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ImportResult:
    """Result of a file import operation."""

    markdown_path: Path
    images: list[Path] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def resolve_output_path(input_path: Path, output_path: Path | None) -> Path:
    """Determine the output .md file path.

    Args:
        input_path: Path to the source file.
        output_path: Explicit output path, directory, or None.

    Returns:
        Resolved path for the output Markdown file.
    """
    if output_path is None:
        return input_path.with_suffix(".md")
    if output_path.is_dir() or not output_path.suffix:
        return output_path / f"{input_path.stem}.md"
    return output_path


def postprocess_markdown(markdown: str) -> str:
    """Clean up generated markdown.

    - Collapses 3+ consecutive newlines to 2
    - Strips trailing whitespace per line
    - Ensures file ends with a single newline
    """
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    markdown = "\n".join(line.rstrip() for line in markdown.split("\n"))
    return markdown.strip() + "\n"


def rows_to_pipe_table(
    rows: list[list[str]],
    alignments: list[str] | None = None,
) -> str:
    """Render a list of rows as a pipe-style Markdown table.

    Args:
        rows: List of rows, each a list of cell strings. First row is the header.
        alignments: Optional list of "left", "center", or "right" per column.

    Returns:
        Pipe-table string (no leading/trailing newlines).
    """
    if not rows:
        return ""

    col_count = max(len(row) for row in rows)
    for row in rows:
        while len(row) < col_count:
            row.append("")

    # Escape pipes in cell content
    for row in rows:
        for i, cell in enumerate(row):
            row[i] = cell.replace("|", "\\|")

    col_widths = [max(len(row[i]) for row in rows) for i in range(col_count)]
    col_widths = [max(w, 3) for w in col_widths]

    lines: list[str] = []
    for idx, row in enumerate(rows):
        cells = [cell.ljust(col_widths[i]) for i, cell in enumerate(row)]
        lines.append("| " + " | ".join(cells) + " |")
        if idx == 0:
            sep_parts = []
            for i, w in enumerate(col_widths):
                align = alignments[i] if alignments and i < len(alignments) else "left"
                if align == "center":
                    sep_parts.append(":" + "-" * (w - 2) + ":")
                elif align == "right":
                    sep_parts.append("-" * (w - 1) + ":")
                else:
                    sep_parts.append("-" * w)
            lines.append("| " + " | ".join(sep_parts) + " |")

    return "\n".join(lines)
