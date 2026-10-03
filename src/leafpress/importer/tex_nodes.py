"""Small helpers for pylatexenc nodes and raw LaTeX used by the LaTeX importer.

Argument and environment-body extraction, tabular cell and column-spec
parsing, and Markdown snippets that need no converter state.
"""

from __future__ import annotations

import functools
import re

from pylatexenc.latexwalker import LatexCharsNode


def ensure_nodelist(node) -> list:
    """Ensure we have a list of nodes from an argument node."""
    if hasattr(node, "nodelist") and node.nodelist is not None:
        return node.nodelist
    if isinstance(node, LatexCharsNode):
        return [node]
    return [node] if node else []


def arg_verbatim(arg) -> str:
    """Verbatim LaTeX of an argument node without its outer braces."""
    text = arg.latex_verbatim() if hasattr(arg, "latex_verbatim") else extract_raw_text(arg)
    text = text.strip()
    if text.startswith("{") and text.endswith("}"):
        text = text[1:-1]
    return text


def extract_raw_text(node) -> str:
    """Extract plain text from a node without recursive markdown conversion."""
    if isinstance(node, LatexCharsNode):
        return node.chars
    if hasattr(node, "nodelist") and node.nodelist:
        return "".join(extract_raw_text(n) for n in node.nodelist)
    if hasattr(node, "chars"):
        return node.chars
    return ""


@functools.lru_cache(maxsize=32)
def _make_env_body_pattern(env_name: str) -> re.Pattern[str]:
    """Compile and cache the regex for extracting an environment body."""
    return re.compile(
        r"\\begin\{"
        + re.escape(env_name)
        + r"\}(?:\[[^\]]*\])*(?:\{[^}]*\})*\s*(.*?)\s*\\end\{"
        + re.escape(env_name)
        + r"\}",
        re.DOTALL,
    )


def extract_env_body_raw(raw_latex: str, env_name: str) -> str:
    """Extract the body between \\begin{env} and \\end{env} from raw LaTeX."""
    match = _make_env_body_pattern(env_name).search(raw_latex)
    if match:
        return match.group(1)
    return raw_latex


def parse_column_alignments(col_spec: str) -> list[str]:
    """Parse LaTeX column spec like '|l|c|r|' into alignment list."""
    alignments = []
    for ch in col_spec:
        if ch == "l":
            alignments.append("left")
        elif ch == "c":
            alignments.append("center")
        elif ch == "r":
            alignments.append("right")
    return alignments


MULTICOLUMN_PATTERN = re.compile(r"\\multicolumn\s*\{(\d+)\}\s*\{[^}]*\}\s*\{(.*)\}", re.DOTALL)


def split_cells(row: str) -> list[str]:
    """Split a tabular row on ``&``, ignoring escaped ``\\&`` and braced groups."""
    cells: list[str] = []
    depth = 0
    start = 0
    i = 0
    while i < len(row):
        ch = row[i]
        if ch == "\\":
            i += 2
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth = max(0, depth - 1)
        elif ch == "&" and depth == 0:
            cells.append(row[start:i])
            start = i + 1
        i += 1
    cells.append(row[start:])
    return cells


def blockquote(text: str) -> str:
    """Render ``text`` as a Markdown blockquote block."""
    lines = text.strip().split("\n")
    return "\n\n" + "\n".join(f"> {line}" if line.strip() else ">" for line in lines) + "\n\n"


def strip_math_labels(math: str) -> str:
    """Remove ``\\label{...}``, ``\\nonumber`` and ``\\notag`` from math source."""
    math = re.sub(r"\\label\s*\{[^}]*\}", "", math)
    return re.sub(r"\\(?:nonumber|notag)\b", "", math)
