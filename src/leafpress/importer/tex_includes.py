"""Expand ``\\input`` / ``\\include`` / ``\\subfile`` / ``\\import`` in LaTeX sources.

Multi-file LaTeX projects split chapters into separate files. Before parsing,
the importer inlines them so the whole document converts as one. Included
paths are confined to the main document's directory tree (the same rule as
``\\includegraphics``), commented-out includes are ignored, and cycles or very
deep nesting are reported instead of recursing forever.
"""

from __future__ import annotations

import re
from pathlib import Path

from leafpress.asset_policy import is_within

MAX_INCLUDE_DEPTH = 20

# \input{f}  \include{f}  \subfile{f}  \import{dir}{f}  \subimport{dir}{f}
_INCLUDE_PATTERN = re.compile(
    r"\\(?P<cmd>input|include|subfile|import|subimport)\s*"
    r"(?:\{(?P<dir>[^{}]*)\}\s*(?=\{))?"
    r"\{(?P<file>[^{}]+)\}"
)
_DOCUMENT_BODY = re.compile(r"\\begin\{document\}(.*?)\\end\{document\}", re.DOTALL)
_INCLUDEONLY = re.compile(r"\\includeonly\s*\{[^{}]*\}")


def _in_comment(text: str, pos: int) -> bool:
    """True if ``pos`` follows an unescaped ``%`` on the same line."""
    line_start = text.rfind("\n", 0, pos) + 1
    return re.search(r"(?<!\\)%", text[line_start:pos]) is not None


def _resolve(base: Path, name: str) -> Path:
    path = base / name.strip()
    if path.suffix != ".tex" and not path.exists():
        path = path.with_suffix(path.suffix + ".tex") if path.suffix else path.with_suffix(".tex")
    return path


def expand_includes(
    content: str, root: Path, warnings: list[str], main_file: Path | None = None
) -> str:
    """Return ``content`` with include commands replaced by the files' text.

    Args:
        content: LaTeX source of the main document.
        root: Directory of the main document; includes resolve against it and
            must stay inside it.
        warnings: Receives a message for each include that is skipped.
        main_file: The main document, so including it again is caught as a cycle.

    Example:
        >>> expand_includes(r"\\input{intro}", Path("paper"), [])  # doctest: +SKIP
    """
    content = _INCLUDEONLY.sub("", content)
    chain = (main_file.resolve(),) if main_file else ()
    return _expand(content, root, root, warnings, chain=chain)


def _expand(
    content: str, base: Path, root: Path, warnings: list[str], chain: tuple[Path, ...]
) -> str:
    def replace(match: re.Match[str]) -> str:
        if _in_comment(content, match.start()):
            return match.group(0)
        cmd, subdir, name = match.group("cmd"), match.group("dir"), match.group("file")
        if cmd in ("import", "subimport") and subdir is None:
            return match.group(0)
        # \import paths are relative to the root; \subimport to the current file
        dir_base = root if cmd == "import" else base
        file_base = dir_base / subdir if subdir else base
        path = _resolve(file_base, name)

        if not is_within(path, root):
            warnings.append(f"\\{cmd}{{{name}}} points outside the document directory; skipped")
            return ""
        resolved = path.resolve()
        if resolved in chain:
            warnings.append(f"\\{cmd}{{{name}}} includes itself (cycle); skipped")
            return ""
        if len(chain) >= MAX_INCLUDE_DEPTH:
            warnings.append(f"\\{cmd}{{{name}}} nested too deeply; skipped")
            return ""
        if not path.is_file():
            warnings.append(f"Included file not found: {name}")
            return ""
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            warnings.append(f"Could not read included file {name}: {e}")
            return ""

        if cmd == "subfile":
            # A subfile is a standalone document; only its body is included
            body = _DOCUMENT_BODY.search(text)
            if body:
                text = body.group(1)
        next_base = path.parent if cmd in ("subimport", "import") else base
        expanded = _expand(text, next_base, root, warnings, (*chain, resolved))
        # \include starts a new page in LaTeX; keep it a separate block here
        return f"\n{expanded}\n" if cmd == "include" else expanded

    return _INCLUDE_PATTERN.sub(replace, content)
