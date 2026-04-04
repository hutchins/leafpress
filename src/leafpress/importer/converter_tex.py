"""LaTeX to Markdown import converter."""

from __future__ import annotations

import copy
import functools
import re
from pathlib import Path

from pylatexenc.latexwalker import (
    LatexCharsNode,
    LatexCommentNode,
    LatexEnvironmentNode,
    LatexGroupNode,
    LatexMacroNode,
    LatexMathNode,
    LatexWalker,
)
from pylatexenc.macrospec import LatexContextDb, MacroSpec
from rich.console import Console

from leafpress.exceptions import TexImportError
from leafpress.importer.base import (
    ImportResult,
    postprocess_markdown,
    resolve_output_path,
    rows_to_pipe_table,
)
from leafpress.importer.image_handler import ImageHandler, content_type_for_extension

console = Console()

# LaTeX macros not in pylatexenc's default database
_EXTRA_MACROS = [
    MacroSpec("href", "{{"),
    MacroSpec("lstinputlisting", "[{"),
    MacroSpec("mintinline", "{{"),
    MacroSpec("captionof", "{{"),
]

_HEADING_MACROS: dict[str, int] = {
    "chapter": 1,
    "section": 2,
    "subsection": 3,
    "subsubsection": 4,
    "paragraph": 5,
    "subparagraph": 6,
}

_FORMAT_MACROS: dict[str, tuple[str, str]] = {
    "textbf": ("**", "**"),
    "textit": ("*", "*"),
    "emph": ("*", "*"),
    "texttt": ("`", "`"),
    "underline": ("<u>", "</u>"),
    "textsc": ("", ""),
}

_SKIP_MACROS: set[str] = {
    "documentclass",
    "usepackage",
    "pagestyle",
    "thispagestyle",
    "setlength",
    "setcounter",
    "addtocounter",
    "newpage",
    "clearpage",
    "cleardoublepage",
    "vspace",
    "hspace",
    "vfill",
    "hfill",
    "noindent",
    "bigskip",
    "medskip",
    "smallskip",
    "centering",
    "raggedright",
    "raggedleft",
    "bibliographystyle",
    "tableofcontents",
    "listoffigures",
    "listoftables",
    "appendix",
    "protect",
    "phantom",
    "hphantom",
    "vphantom",
}

_DEFINITION_MACROS: set[str] = {
    "newcommand",
    "renewcommand",
    "providecommand",
    "def",
    "let",
    "newenvironment",
    "renewenvironment",
}

_MATH_ENVS: set[str] = {
    "equation",
    "equation*",
    "align",
    "align*",
    "gather",
    "gather*",
    "multline",
    "multline*",
    "eqnarray",
    "eqnarray*",
    "flalign",
    "flalign*",
    "math",
    "displaymath",
}

_SKIP_ENVS: set[str] = {
    "tikzpicture",
    "pgfpicture",
    "frame",
}

_IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".svg", ".gif", ".bmp", ".webp"]
_UNSUPPORTED_IMAGE_EXTENSIONS = {".pdf", ".eps", ".ps"}

# Pre-compiled patterns for code block language detection
_LSTLISTING_LANG_RE = re.compile(r"\[.*?language\s*=\s*(\w+)")
_MINTED_LANG_RE = re.compile(r"\\begin\{minted\}(?:\[.*?\])?\{(\w+)\}")

# Module-level cached latex context (built once, never mutated after init)
_LATEX_CONTEXT: LatexContextDb | None = None


def _get_latex_context() -> LatexContextDb:
    """Return a latex context with extra macro definitions.

    Uses a deep copy of the default context to avoid mutating the shared
    pylatexenc singleton. The result is cached for reuse.
    """
    global _LATEX_CONTEXT
    if _LATEX_CONTEXT is None:
        from pylatexenc.latexwalker import get_default_latex_context_db

        ctx = copy.deepcopy(get_default_latex_context_db())
        ctx.add_context_category("leafpress-extra", macros=_EXTRA_MACROS)
        _LATEX_CONTEXT = ctx
    return _LATEX_CONTEXT


def import_tex(
    tex_path: Path,
    output_path: Path | None = None,
    extract_images: bool = True,
) -> ImportResult:
    """Convert a LaTeX file to Markdown.

    Args:
        tex_path: Path to the input .tex file.
        output_path: Output .md file path or directory. If None, uses
                      tex_path stem + .md in the same directory.
        extract_images: Whether to extract/copy images to assets/.

    Returns:
        ImportResult with paths to generated files and any warnings.

    Raises:
        TexImportError: If the input file is invalid or conversion fails.
    """
    if not tex_path.exists():
        raise TexImportError(f"File not found: {tex_path}")
    if tex_path.suffix.lower() != ".tex":
        raise TexImportError(f"Not a .tex file: {tex_path}")

    md_path = resolve_output_path(tex_path, output_path)

    assets_dir = md_path.parent / "assets" if extract_images else None
    image_handler = ImageHandler(assets_dir) if assets_dir else None

    with console.status("[bold blue]Converting LaTeX to Markdown..."):
        try:
            latex_content = tex_path.read_text(encoding="utf-8")
        except Exception as e:
            raise TexImportError(f"Failed to read LaTeX file: {e}") from e

        try:
            converter = _TexToMarkdownConverter(
                tex_dir=tex_path.parent,
                image_handler=image_handler,
            )
            markdown = converter.convert(latex_content)
        except TexImportError:
            raise
        except Exception as e:
            raise TexImportError(f"Failed to convert LaTeX: {e}") from e

    markdown = postprocess_markdown(markdown)

    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(markdown, encoding="utf-8")

    return ImportResult(
        markdown_path=md_path,
        images=image_handler.saved_images if image_handler else [],
        warnings=converter.warnings,
    )


class _TexToMarkdownConverter:
    """Walks a pylatexenc AST and produces Markdown."""

    def __init__(
        self,
        tex_dir: Path,
        image_handler: ImageHandler | None,
    ) -> None:
        self._tex_dir = tex_dir
        self._image_handler = image_handler
        self._warnings: list[str] = []
        self._warned_macros: set[str] = set()
        self._warned_envs: set[str] = set()
        self._in_document = False
        self._list_depth = 0
        self._list_ordered: list[bool] = []
        self._list_counters: list[int] = []
        self._title: str = ""
        self._author: str = ""
        self._date: str = ""
        self._footnote_counter = 0
        self._footnotes: list[str] = []
        self._figure_caption: str = ""

    @property
    def warnings(self) -> list[str]:
        return list(self._warnings)

    def convert(self, latex_content: str) -> str:
        ctx = _get_latex_context()
        walker = LatexWalker(latex_content, latex_context=ctx, tolerant_parsing=True)
        nodes, _pos, _ln = walker.get_latex_nodes()

        if not self._has_document_environment(nodes):
            self._in_document = True

        result = self._convert_nodes(nodes)

        if self._footnotes:
            result += "\n\n" + "\n".join(self._footnotes)

        return result

    def _has_document_environment(self, nodes: list | None) -> bool:
        if not nodes:
            return False
        return any(
            isinstance(n, LatexEnvironmentNode) and n.environmentname == "document" for n in nodes
        )

    def _convert_nodes(self, nodes: list | None) -> str:
        if not nodes:
            return ""
        parts = []
        for node in nodes:
            part = self._convert_node(node)
            if part is not None:
                parts.append(part)
        return "".join(parts)

    def _convert_node(self, node) -> str:
        if isinstance(node, LatexCharsNode):
            if not self._in_document:
                return ""
            return node.chars

        if isinstance(node, LatexCommentNode):
            return ""

        if isinstance(node, LatexGroupNode):
            return self._convert_nodes(node.nodelist)

        if isinstance(node, LatexMathNode):
            if not self._in_document:
                return ""
            return self._convert_math(node)

        if isinstance(node, LatexMacroNode):
            return self._convert_macro(node)

        if isinstance(node, LatexEnvironmentNode):
            return self._convert_environment(node)

        return ""

    # -- Math --

    def _convert_math(self, node: LatexMathNode) -> str:
        raw = node.latex_verbatim()
        if node.displaytype == "inline":
            return raw
        return f"\n\n{raw}\n\n"

    # -- Macros --

    def _convert_macro(self, node: LatexMacroNode) -> str:
        name = node.macroname

        if name in _HEADING_MACROS:
            return self._convert_heading(node)

        if name in _FORMAT_MACROS:
            return self._convert_formatting(node)

        if name == "href":
            return self._convert_href(node)
        if name == "url":
            return self._convert_url(node)

        if name == "includegraphics":
            return self._convert_includegraphics(node)

        # Metadata — may appear in preamble, so use raw text extraction
        if name == "title":
            self._title = self._get_macro_arg_raw(node)
            return ""
        if name == "author":
            self._author = self._get_macro_arg_raw(node)
            return ""
        if name == "date":
            self._date = self._get_macro_arg_raw(node)
            return ""
        if name == "maketitle":
            return self._emit_title_block()

        if name == "label":
            return ""
        if name in ("ref", "eqref", "autoref"):
            key = self._get_macro_arg_raw(node)
            return f"[ref:{key}]"
        if name in ("cite", "citep", "citet", "citeyear"):
            key = self._get_macro_arg_raw(node)
            return f"[{key}]"

        if name == "footnote":
            return self._convert_footnote(node)

        if name == "item":
            return self._convert_item(node)

        if name == "caption":
            self._figure_caption = self._get_macro_arg(node)
            return ""

        if name == "\\":
            return "\n"

        if name in _SKIP_MACROS:
            return ""

        if name in _DEFINITION_MACROS:
            if name not in self._warned_macros:
                self._warnings.append(
                    f"Custom macro definition '\\{name}' skipped — usages may appear as raw text"
                )
                self._warned_macros.add(name)
            return ""

        if name not in self._warned_macros:
            self._warnings.append(f"Unknown macro '\\{name}' — rendering arguments as plain text")
            self._warned_macros.add(name)
        return self._get_macro_arg(node)

    def _convert_heading(self, node: LatexMacroNode) -> str:
        level = _HEADING_MACROS[node.macroname]
        text = self._get_macro_arg(node).strip()
        prefix = "#" * level
        return f"\n\n{prefix} {text}\n\n"

    def _convert_formatting(self, node: LatexMacroNode) -> str:
        pre, suf = _FORMAT_MACROS[node.macroname]
        content = self._get_macro_arg(node)
        return f"{pre}{content}{suf}"

    def _convert_href(self, node: LatexMacroNode) -> str:
        args = self._get_all_macro_args(node)
        if len(args) >= 2:
            return f"[{args[1]}]({args[0]})"
        return self._get_macro_arg(node)

    def _convert_url(self, node: LatexMacroNode) -> str:
        url = self._get_macro_arg_raw(node)
        return f"<{url}>"

    def _convert_includegraphics(self, node: LatexMacroNode) -> str:
        if not self._image_handler:
            return ""

        image_path_str = self._get_macro_arg_raw(node)
        if not image_path_str:
            return ""

        image_path = self._resolve_image_path(image_path_str)
        if image_path is None:
            self._warnings.append(f"Image not found: {image_path_str}")
            return f"![{image_path_str}]({image_path_str})"

        if image_path.suffix.lower() in _UNSUPPORTED_IMAGE_EXTENSIONS:
            self._warnings.append(
                f"Unsupported image format '{image_path.suffix}': {image_path_str}"
            )
            return f"![{image_path_str}]({image_path_str})"

        try:
            image_bytes = image_path.read_bytes()
            content_type = content_type_for_extension(image_path.suffix.lower())
            src = self._image_handler.save_image(image_bytes, content_type)
            return f"![]({src})"
        except Exception as e:
            self._warnings.append(f"Failed to copy image {image_path_str}: {e}")
            return f"![{image_path_str}]({image_path_str})"

    def _resolve_image_path(self, path_str: str) -> Path | None:
        path = self._tex_dir / path_str
        if path.exists():
            return path
        if not path.suffix:
            for ext in _IMAGE_EXTENSIONS:
                candidate = path.with_suffix(ext)
                if candidate.exists():
                    return candidate
        return None

    def _convert_footnote(self, node: LatexMacroNode) -> str:
        self._footnote_counter += 1
        n = self._footnote_counter
        content = self._get_macro_arg(node).strip()
        self._footnotes.append(f"[^{n}]: {content}")
        return f"[^{n}]"

    def _convert_item(self, node: LatexMacroNode) -> str:
        label = self._get_optional_arg(node)
        indent = "  " * max(0, self._list_depth - 1)
        if label:
            return f"\n{indent}**{label}**: "

        # Emit numbered marker for ordered lists, bullet for unordered
        if self._list_ordered and self._list_ordered[-1]:
            self._list_counters[-1] += 1
            return f"\n{indent}{self._list_counters[-1]}. "
        return f"\n{indent}- "

    def _emit_title_block(self) -> str:
        parts = []
        if self._title:
            parts.append(f"# {self._title}")
        if self._author:
            parts.append(f"*{self._author}*")
        if self._date:
            parts.append(f"*{self._date}*")
        if parts:
            return "\n\n".join(parts) + "\n\n"
        return ""

    # -- Environments --

    def _convert_environment(self, node: LatexEnvironmentNode) -> str:
        name = node.environmentname

        if name == "document":
            self._in_document = True
            return self._convert_nodes(node.nodelist)

        if name in _MATH_ENVS:
            return self._convert_math_env(node)

        if name in ("itemize", "enumerate"):
            return self._convert_list(node, ordered=name == "enumerate")
        if name == "description":
            return self._convert_list(node, ordered=False)

        if name in ("verbatim", "lstlisting", "minted"):
            return self._convert_code_block(node)

        if name in ("tabular", "tabular*"):
            return self._convert_tabular(node)

        if name in ("figure", "figure*"):
            return self._convert_figure(node)

        if name in ("abstract", "quote", "quotation"):
            return self._convert_blockquote(node)

        if name in ("center", "flushleft", "flushright", "minipage"):
            return self._convert_nodes(node.nodelist)

        if name in _SKIP_ENVS:
            if name not in self._warned_envs:
                self._warnings.append(f"Unsupported environment '{name}' skipped")
                self._warned_envs.add(name)
            return ""

        if name not in self._warned_envs:
            self._warnings.append(f"Unknown environment '{name}' — rendering body as plain text")
            self._warned_envs.add(name)
        return self._convert_nodes(node.nodelist)

    def _convert_math_env(self, node: LatexEnvironmentNode) -> str:
        raw = node.latex_verbatim()
        inner = _extract_env_body_raw(raw, node.environmentname)
        return f"\n\n$${inner}$$\n\n"

    def _convert_list(self, node: LatexEnvironmentNode, *, ordered: bool) -> str:
        self._list_depth += 1
        self._list_ordered.append(ordered)
        self._list_counters.append(0)

        body = self._convert_nodes(node.nodelist)

        self._list_depth -= 1
        self._list_ordered.pop()
        self._list_counters.pop()
        return f"\n{body}\n"

    def _convert_code_block(self, node: LatexEnvironmentNode) -> str:
        """Convert verbatim, lstlisting, or minted to a fenced code block."""
        raw = node.latex_verbatim()
        inner = _extract_env_body_raw(raw, node.environmentname)

        lang = ""
        if node.environmentname == "lstlisting":
            match = _LSTLISTING_LANG_RE.search(raw)
            if match:
                lang = match.group(1).lower()
        elif node.environmentname == "minted":
            match = _MINTED_LANG_RE.match(raw)
            if match:
                lang = match.group(1).lower()

        return f"\n\n```{lang}\n{inner.strip()}\n```\n\n"

    def _convert_tabular(self, node: LatexEnvironmentNode) -> str:
        raw = node.latex_verbatim()
        inner = _extract_env_body_raw(raw, node.environmentname)

        col_spec = ""
        begin_match = re.match(
            r"\\begin\{" + re.escape(node.environmentname) + r"\}\s*\{([^}]*)\}", raw
        )
        if begin_match:
            col_spec = begin_match.group(1)

        alignments = _parse_column_alignments(col_spec)

        row_strs = re.split(r"\\\\", inner)
        rows: list[list[str]] = []
        for row_str in row_strs:
            row_str = row_str.strip()
            if not row_str:
                continue
            row_str = re.sub(
                r"\\(?:hline|toprule|midrule|bottomrule|cline\{[^}]*\})\s*", "", row_str
            ).strip()
            if not row_str:
                continue
            cells = [c.strip() for c in row_str.split("&")]
            rows.append(cells)

        if not rows:
            return ""

        table = rows_to_pipe_table(rows, alignments=alignments)
        return f"\n\n{table}\n\n"

    def _convert_figure(self, node: LatexEnvironmentNode) -> str:
        self._figure_caption = ""

        body = self._convert_nodes(node.nodelist)

        if self._figure_caption and "![](" in body:
            body = body.replace("![](", f"![{self._figure_caption}](", 1)
        elif self._figure_caption and body.strip():
            body = body.strip() + f"\n\n*{self._figure_caption}*"

        return f"\n\n{body.strip()}\n\n"

    def _convert_blockquote(self, node: LatexEnvironmentNode) -> str:
        body = self._convert_nodes(node.nodelist).strip()
        quoted = "\n".join(f"> {line}" for line in body.split("\n"))
        return f"\n\n{quoted}\n\n"

    # -- Argument extraction helpers --

    def _find_macro_arg(self, node: LatexMacroNode, index: int = -1):
        """Find and return the raw argument node at the given index.

        If index is -1, returns the last non-None argument (the main required arg).
        Returns None if no argument is found.
        """
        if not node.nodeargd or not node.nodeargd.argnlist:
            return None

        if index >= 0:
            if index < len(node.nodeargd.argnlist):
                return node.nodeargd.argnlist[index]
            return None

        for arg in reversed(node.nodeargd.argnlist):
            if arg is not None:
                return arg
        return None

    def _get_macro_arg(self, node: LatexMacroNode, index: int = -1) -> str:
        """Get the converted content of a macro's argument."""
        arg = self._find_macro_arg(node, index)
        if arg is None:
            return ""
        return self._convert_nodes(_ensure_nodelist(arg))

    def _get_macro_arg_raw(self, node: LatexMacroNode, index: int = -1) -> str:
        """Get the raw text of a macro's argument (not recursively converted)."""
        arg = self._find_macro_arg(node, index)
        if arg is None:
            return ""
        return _extract_raw_text(arg)

    def _get_all_macro_args(self, node: LatexMacroNode) -> list[str]:
        """Get all non-None macro arguments as converted strings."""
        if not node.nodeargd or not node.nodeargd.argnlist:
            return []
        return [
            self._convert_nodes(_ensure_nodelist(arg))
            for arg in node.nodeargd.argnlist
            if arg is not None
        ]

    def _get_optional_arg(self, node: LatexMacroNode) -> str:
        """Get the optional [...] argument of a macro, if present."""
        if not node.nodeargd or not node.nodeargd.argnlist:
            return ""
        for arg in node.nodeargd.argnlist:
            if arg is not None and hasattr(arg, "delimiters"):
                delims = arg.delimiters
                if delims and delims[0] == "[":
                    return self._convert_nodes(_ensure_nodelist(arg))
        return ""


# -- Module-level helpers --


def _ensure_nodelist(node) -> list:
    """Ensure we have a list of nodes from an argument node."""
    if hasattr(node, "nodelist") and node.nodelist is not None:
        return node.nodelist
    if isinstance(node, LatexCharsNode):
        return [node]
    return [node] if node else []


def _extract_raw_text(node) -> str:
    """Extract plain text from a node without recursive markdown conversion."""
    if isinstance(node, LatexCharsNode):
        return node.chars
    if hasattr(node, "nodelist") and node.nodelist:
        return "".join(_extract_raw_text(n) for n in node.nodelist)
    if hasattr(node, "chars"):
        return node.chars
    return ""


@functools.lru_cache(maxsize=32)
def _make_env_body_pattern(env_name: str) -> re.Pattern[str]:
    """Compile and cache the regex for extracting an environment body."""
    return re.compile(
        r"\\begin\{"
        + re.escape(env_name)
        + r"\}(?:\[[^\]]*\])*(?:\{[^}]*\})?\s*(.*?)\s*\\end\{"
        + re.escape(env_name)
        + r"\}",
        re.DOTALL,
    )


def _extract_env_body_raw(raw_latex: str, env_name: str) -> str:
    """Extract the body between \\begin{env} and \\end{env} from raw LaTeX."""
    match = _make_env_body_pattern(env_name).search(raw_latex)
    if match:
        return match.group(1)
    return raw_latex


def _parse_column_alignments(col_spec: str) -> list[str]:
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
