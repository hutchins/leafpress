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
    LatexSpecialsNode,
    LatexWalker,
)
from pylatexenc.macrospec import EnvironmentSpec, LatexContextDb, MacroSpec
from rich.console import Console

from leafpress.asset_policy import is_within
from leafpress.exceptions import TexImportError
from leafpress.importer.base import (
    ImportResult,
    postprocess_markdown,
    resolve_output_path,
    rows_to_pipe_table,
)
from leafpress.importer.image_handler import ImageHandler, content_type_for_extension
from leafpress.importer.tex_includes import expand_includes
from leafpress.importer.tex_symbols import (
    ACCENT_MARKS,
    SYMBOL_MACROS,
    apply_accent,
    apply_ligatures,
    format_si_number,
    format_si_quantity,
    format_si_range,
    format_si_unit,
)

console = Console()

# LaTeX macros missing (or missing arguments) in pylatexenc's default
# database. Registered ahead of the defaults so these argument specs win.
_EXTRA_MACROS = [
    MacroSpec("href", "{{"),
    MacroSpec("lstinputlisting", "[{"),
    MacroSpec("mintinline", "{{"),
    MacroSpec("captionof", "{{"),
    # Structure and captions
    MacroSpec("paragraph", "*[{"),
    MacroSpec("subparagraph", "*[{"),
    MacroSpec("caption", "[{"),
    MacroSpec("subcaption", "[{"),
    MacroSpec("subfloat", "[[{"),
    MacroSpec("multicolumn", "{{{"),
    MacroSpec("newtheorem", "*{[{["),
    MacroSpec("texorpdfstring", "{{"),
    MacroSpec("textsuperscript", "{"),
    MacroSpec("textsubscript", "{"),
    # Cross-references (cleveref / hyperref)
    MacroSpec("cref", "*{"),
    MacroSpec("Cref", "*{"),
    MacroSpec("nameref", "{"),
    MacroSpec("pageref", "{"),
    # siunitx (v2 and v3 names)
    MacroSpec("SI", "[{[{"),
    MacroSpec("qty", "[{{"),
    MacroSpec("si", "[{"),
    MacroSpec("unit", "[{"),
    MacroSpec("num", "[{"),
    MacroSpec("ang", "[{"),
    MacroSpec("SIrange", "[{{{"),
    MacroSpec("qtyrange", "[{{{"),
    MacroSpec("numrange", "[{{"),
    # Beamer
    MacroSpec("frametitle", "[{"),
    MacroSpec("framesubtitle", "{"),
    MacroSpec("only", "{"),
    MacroSpec("visible", "{"),
    MacroSpec("uncover", "{"),
    MacroSpec("onslide", "{"),
    MacroSpec("invisible", "{"),
    MacroSpec("alert", "{"),
    MacroSpec("note", "[{"),
    # Accents without a default spec
    *(MacroSpec(accent, "{") for accent in ("=", ".", "u", "v", "H", "r", "d", "b", "k")),
]

_EXTRA_ENVIRONMENTS = [
    EnvironmentSpec("subfigure", "[{"),
    EnvironmentSpec("block", "{"),
    EnvironmentSpec("alertblock", "{"),
    EnvironmentSpec("exampleblock", "{"),
    EnvironmentSpec("column", "[{"),
    EnvironmentSpec("columns", "["),
]

# Theorem-like environments recognized without a \newtheorem declaration
_DEFAULT_THEOREMS: dict[str, str] = {
    "theorem": "Theorem",
    "lemma": "Lemma",
    "proposition": "Proposition",
    "corollary": "Corollary",
    "definition": "Definition",
    "remark": "Remark",
    "example": "Example",
    "conjecture": "Conjecture",
    "claim": "Claim",
    "exercise": "Exercise",
    "assumption": "Assumption",
    "axiom": "Axiom",
    "observation": "Observation",
    "note": "Note",
    "problem": "Problem",
    "solution": "Solution",
}

_REF_MACROS = {"ref", "eqref", "autoref", "cref", "Cref", "nameref", "pageref"}

# Beamer overlay specs (<2->, <+->) after these commands, and [<+->] list options
_OVERLAY_SPEC_PATTERN = re.compile(
    r"(\\(?:item|only|visible|uncover|onslide|invisible|alert|pause|action|"
    r"textbf|textit|emph|includegraphics|color|structure|"
    r"begin\{(?:itemize|enumerate|description|block|alertblock|exampleblock|frame)\}))"
    r"\s*<[^<>\n]*>"
)
_LIST_OVERLAY_OPTION_PATTERN = re.compile(
    r"(\\begin\{(?:itemize|enumerate|description)\})\s*\[<[^\]]*>\]"
)

# Placeholder for cross-references, resolved after the whole document is seen
_REF_PLACEHOLDER = re.compile("\x00REF:(\\w+):([^\x00]*)\x00")

_MULTIROW_MATH_ENVS = {"align", "gather", "eqnarray", "flalign"}
_SINGLE_ROW_NUMBERED_ENVS = {"equation", "multline"}

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
        ctx.add_context_category(
            "leafpress-extra",
            macros=_EXTRA_MACROS,
            environments=_EXTRA_ENVIRONMENTS,
            prepend=True,
        )
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
            latex_content = expand_includes(
                latex_content, tex_path.parent, converter.include_warnings, main_file=tex_path
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
    """Walks a pylatexenc AST and produces Markdown.

    Cross-references are emitted as placeholders during the walk and resolved
    at the end, once every ``\\label`` (including forward ones) is known.
    """

    def __init__(
        self,
        tex_dir: Path,
        image_handler: ImageHandler | None,
    ) -> None:
        self._tex_dir = tex_dir
        self._image_handler = image_handler
        self._warnings: list[str] = []
        # Filled by expand_includes() before convert() runs
        self.include_warnings: list[str] = []
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
        # Text inside \texttt etc. keeps "--" and quotes literal
        self._literal_text_depth = 0
        # Numbering for cross-references
        self._heading_counters = [0] * 7  # index = heading level
        self._has_chapters = False
        self._figure_counter = 0
        self._table_counter = 0
        self._equation_counter = 0
        self._subfigure_counter = 0
        self._in_figure = False
        self._in_subfigure = False
        self._in_table = False
        self._theorem_names: dict[str, str] = dict(_DEFAULT_THEOREMS)
        self._theorem_counter_owner: dict[str, str] = {}
        self._theorem_counters: dict[str, int] = {}
        # label key -> (kind, number, title); kind is a display name like "Section"
        self._labels: dict[str, tuple[str, str, str]] = {}
        # What a \label right now would refer to
        self._label_target: tuple[str, str, str] | None = None
        self._seen_section = False
        self._warned_multicolumn = False

    @property
    def warnings(self) -> list[str]:
        return [*self.include_warnings, *self._warnings]

    def convert(self, latex_content: str) -> str:
        latex_content = _LIST_OVERLAY_OPTION_PATTERN.sub(r"\1", latex_content)
        latex_content = _OVERLAY_SPEC_PATTERN.sub(r"\1", latex_content)
        self._has_chapters = "\\chapter" in latex_content

        ctx = _get_latex_context()
        walker = LatexWalker(latex_content, latex_context=ctx, tolerant_parsing=True)
        nodes, _pos, _ln = walker.get_latex_nodes()

        if not self._has_document_environment(nodes):
            self._in_document = True

        result = self._convert_nodes(nodes)

        if self._footnotes:
            result += "\n\n" + "\n".join(self._footnotes)

        return self._resolve_references(result)

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
            if self._literal_text_depth:
                return node.chars
            return apply_ligatures(node.chars)

        if isinstance(node, LatexSpecialsNode):
            # ~, --, ---, ``, '' (and & outside tables) are parsed as "specials"
            if not self._in_document:
                return ""
            chars = node.specials_chars
            return chars if self._literal_text_depth else apply_ligatures(chars)

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

    def _convert_fragment(self, latex: str) -> str:
        """Convert a standalone LaTeX snippet (e.g. a table cell) to Markdown."""
        walker = LatexWalker(latex, latex_context=_get_latex_context(), tolerant_parsing=True)
        nodes, _pos, _ln = walker.get_latex_nodes()
        return self._convert_nodes(nodes)

    # -- Math --

    def _convert_math(self, node: LatexMathNode) -> str:
        raw = _strip_math_labels(node.latex_verbatim())
        if node.displaytype == "inline":
            return raw
        return f"\n\n{raw}\n\n"

    # -- Cross-references --

    def _set_label_target(self, kind: str, number: str, title: str = "") -> None:
        self._label_target = (kind, number, title)

    def _record_label(self, key: str) -> None:
        if self._label_target is not None:
            self._labels[key] = self._label_target

    def _ref_placeholder(self, macro: str, node: LatexMacroNode) -> str:
        keys = self._get_macro_arg_raw(node)
        return "\x00REF:" + macro + ":" + keys + "\x00"

    def _resolve_references(self, text: str) -> str:
        unresolved: set[str] = set()

        def resolve_one(macro: str, key: str) -> str:
            label = self._labels.get(key)
            if label is None or macro == "pageref":
                unresolved.add(key)
                return f"[ref:{key}]"
            kind, number, title = label
            if macro == "eqref" or (kind == "Equation" and macro != "ref"):
                shown = f"({number})"
            else:
                shown = number
            if macro == "nameref":
                return title or shown
            if macro in ("autoref", "cref", "Cref"):
                return f"{kind} {shown}"
            return shown

        def replace(match: re.Match[str]) -> str:
            macro, keys = match.group(1), match.group(2)
            # \cref{a,b} lists several labels
            return ", ".join(resolve_one(macro, k.strip()) for k in keys.split(",") if k.strip())

        result = _REF_PLACEHOLDER.sub(replace, text)
        if unresolved:
            self._warnings.append(
                "Unresolved references (shown as [ref:key]): " + ", ".join(sorted(unresolved))
            )
        return result

    # -- Macros --

    def _convert_macro(self, node: LatexMacroNode) -> str:
        name = node.macroname

        if name in _HEADING_MACROS:
            return self._convert_heading(node)

        if name in _FORMAT_MACROS:
            return self._convert_formatting(node)

        if name in ACCENT_MARKS and node.nodeargd and node.nodeargd.argnlist:
            return apply_accent(name, self._get_macro_arg(node))

        if name in SYMBOL_MACROS:
            return SYMBOL_MACROS[name]

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
        if name in ("maketitle", "titlepage"):
            return self._emit_title_block()

        if name == "label":
            self._record_label(self._get_macro_arg_raw(node).strip())
            return ""
        if name in _REF_MACROS:
            return self._ref_placeholder(name, node)
        if name in ("cite", "citep", "citet", "citeyear"):
            key = self._get_macro_arg_raw(node)
            return f"[{key}]"

        if name == "footnote":
            return self._convert_footnote(node)

        if name == "item":
            return self._convert_item(node)

        if name == "caption":
            return self._convert_caption(node)
        if name == "subcaption":
            self._figure_caption = self._get_macro_arg(node)
            return ""

        if name == "\\":
            return "\n"

        # siunitx
        if name in ("SI", "qty"):
            args = self._get_required_args_raw(node)
            return format_si_quantity(args[0], args[-1]) if len(args) >= 2 else ""
        if name in ("si", "unit"):
            return format_si_unit(self._get_macro_arg_verbatim(node))
        if name == "num":
            return format_si_number(self._get_macro_arg_verbatim(node))
        if name == "ang":
            return format_si_number(self._get_macro_arg_verbatim(node)) + "°"
        if name in ("SIrange", "qtyrange", "numrange"):
            args = self._get_required_args_raw(node)
            if len(args) >= 2:
                return format_si_range(args[0], args[1], args[2] if len(args) > 2 else "")
            return ""

        if name == "multicolumn":
            # Outside a tabular (handled there) just keep the content
            return self._get_macro_arg(node)
        if name == "subfloat":
            return self._convert_subfloat(node)
        if name == "texorpdfstring":
            return self._get_macro_arg(node, 0)
        if name == "textsuperscript":
            return f"<sup>{self._get_macro_arg(node)}</sup>"
        if name == "textsubscript":
            return f"<sub>{self._get_macro_arg(node)}</sub>"
        if name in ("qed", "qedsymbol"):
            return " ∎"

        # Beamer
        if name in ("only", "visible", "uncover", "onslide"):
            return self._get_macro_arg(node)
        if name in ("invisible", "pause", "qedhere", "theoremstyle", "usetheme", "usecolortheme"):
            return ""
        if name == "alert":
            return f"**{self._get_macro_arg(node)}**"
        if name == "note":
            text = self._get_macro_arg(node).strip()
            return f"\n\n> **Note:** {text}\n\n" if text else ""
        if name == "frametitle":
            return self._frame_heading(self._get_macro_arg(node).strip())
        if name == "framesubtitle":
            return f"*{self._get_macro_arg(node).strip()}*\n\n"

        if name == "newtheorem":
            self._register_theorem(node)
            return ""

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
        if node.macroname in ("section", "chapter"):
            self._seen_section = True
        starred = bool(node.nodeargd and node.nodeargd.argnlist and node.nodeargd.argnlist[0])
        if not starred:
            self._heading_counters[level] += 1
            for deeper in range(level + 1, len(self._heading_counters)):
                self._heading_counters[deeper] = 0
            first = 1 if self._has_chapters else 2
            number = ".".join(str(n) for n in self._heading_counters[first : level + 1])
            kind = "Chapter" if node.macroname == "chapter" else "Section"
            self._set_label_target(kind, number, text)
        prefix = "#" * level
        return f"\n\n{prefix} {text}\n\n"

    def _convert_formatting(self, node: LatexMacroNode) -> str:
        pre, suf = _FORMAT_MACROS[node.macroname]
        literal = node.macroname == "texttt"
        self._literal_text_depth += literal
        try:
            content = self._get_macro_arg(node)
        finally:
            self._literal_text_depth -= literal
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
        """Find an \\\\includegraphics file, confined to the .tex file's directory.

        Absolute paths, ``..`` traversal, and symlinks leading outside are
        rejected so importing a third-party .tex can't copy arbitrary local
        files into the output ``assets/`` folder.
        """
        path = self._tex_dir / path_str
        candidates = [path]
        if not path.suffix:
            candidates += [path.with_suffix(ext) for ext in _IMAGE_EXTENSIONS]
        for candidate in candidates:
            if candidate.exists():
                if not is_within(candidate, self._tex_dir):
                    self._warnings.append(f"Image outside the source directory skipped: {path_str}")
                    return None
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

    def _convert_caption(self, node: LatexMacroNode) -> str:
        """Record a figure/table caption and number it (as LaTeX's \\caption does)."""
        text = self._get_macro_arg(node).strip()
        if self._in_table:
            self._table_counter += 1
            number = str(self._table_counter)
            self._set_label_target("Table", number, text)
            return f"\n\n*Table {number}: {text}*\n\n"
        if self._in_subfigure:
            # subcaption's subfigure uses a plain \caption for the sub-caption
            self._figure_caption = text
            return ""
        if self._in_figure:
            self._figure_counter += 1
            self._set_label_target("Figure", str(self._figure_counter), text)
        self._figure_caption = text
        return ""

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

        if name in ("tabular", "tabular*", "tabularx"):
            return self._convert_tabular(node)

        if name in ("figure", "figure*", "wrapfigure"):
            return self._convert_figure(node)
        if name == "subfigure":
            return self._convert_subfigure(node)
        if name in ("table", "table*"):
            return self._convert_table(node)

        if name in ("abstract", "quote", "quotation"):
            return self._convert_blockquote(node)

        if name in ("center", "flushleft", "flushright", "minipage", "columns", "column"):
            return self._convert_nodes(node.nodelist)

        if name.rstrip("*") in self._theorem_names:
            return self._convert_theorem(node)
        if name == "proof":
            return self._convert_proof(node)

        if name == "frame":
            return self._convert_frame(node)
        if name in ("block", "alertblock", "exampleblock"):
            return self._convert_block(node)

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
        """Convert a display-math environment to ``$$...$$``.

        Numbered environments get explicit ``\\tag{n}`` so equation numbers
        (and ``\\eqref`` targets) survive; ``\\label``/``\\nonumber`` are removed.
        """
        name = node.environmentname
        base = name.rstrip("*")
        numbered = not name.endswith("*")
        inner = _extract_env_body_raw(node.latex_verbatim(), name)

        if base in _MULTIROW_MATH_ENVS:
            rows = re.split(r"\\\\", inner)
            if numbered:
                rows = [self._number_math_row(row) for row in rows]
                body = "\\\\".join(rows).strip()
                return f"\n\n$$\n\\begin{{{base}}}\n{body}\n\\end{{{base}}}\n$$\n\n"
            wrapper = "gathered" if base == "gather" else "aligned"
            body = "\\\\".join(_strip_math_labels(r) for r in rows).strip()
            return f"\n\n$$\n\\begin{{{wrapper}}}\n{body}\n\\end{{{wrapper}}}\n$$\n\n"

        if numbered and base in _SINGLE_ROW_NUMBERED_ENVS:
            body = self._number_math_row(inner).strip()
            return f"\n\n$${body}$$\n\n"
        return f"\n\n$${_strip_math_labels(inner).strip()}$$\n\n"

    def _number_math_row(self, row: str) -> str:
        """Tag one numbered equation row and record any \\label on it."""
        if not row.strip() or re.search(r"\\(?:nonumber|notag)\b", row):
            return _strip_math_labels(row)
        self._equation_counter += 1
        number = str(self._equation_counter)
        for key in re.findall(r"\\label\{([^}]*)\}", row):
            self._labels[key.strip()] = ("Equation", number, "")
        return f"{_strip_math_labels(row).rstrip()} \\tag{{{number}}}"

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
            r"\\begin\{" + re.escape(node.environmentname) + r"\}\s*(?:\{[^}]*\}\s*)?\{([^}]*)\}"
            if node.environmentname in ("tabular*", "tabularx")
            else r"\\begin\{" + re.escape(node.environmentname) + r"\}\s*\{([^}]*)\}",
            raw,
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
            cells: list[str] = []
            for cell in _split_cells(row_str):
                span = _MULTICOLUMN_PATTERN.fullmatch(cell.strip())
                if span:
                    count, content = int(span.group(1)), span.group(2)
                    cells.append(self._convert_fragment(content).strip())
                    # Pipe tables can't span columns; pad with empty cells
                    cells.extend([""] * (count - 1))
                    if count > 1 and not self._warned_multicolumn:
                        self._warnings.append(
                            "\\multicolumn spans flattened: content kept in the first column"
                        )
                        self._warned_multicolumn = True
                else:
                    cells.append(self._convert_fragment(cell).strip())
            rows.append(cells)

        if not rows:
            return ""

        table = rows_to_pipe_table(rows, alignments=alignments)
        return f"\n\n{table}\n\n"

    def _convert_figure(self, node: LatexEnvironmentNode) -> str:
        outer_in_figure, self._in_figure = self._in_figure, True
        self._figure_caption = ""
        self._subfigure_counter = 0
        try:
            body = self._convert_nodes(node.nodelist)
        finally:
            self._in_figure = outer_in_figure

        # _convert_nodes() sets _figure_caption as a side effect when it meets
        # \caption, which ty's narrowing doesn't model.
        caption = self._figure_caption
        number = self._figure_counter
        if caption and "![](" in body:  # ty: ignore[redundant-condition]
            body = body.replace("![](", f"![{caption}](", 1)
        if caption:  # ty: ignore[redundant-condition]
            body = body.strip() + f"\n\n*Figure {number}: {caption}*"

        return f"\n\n{body.strip()}\n\n"

    def _convert_subfigure(self, node: LatexEnvironmentNode) -> str:
        """Render one sub-figure: its image (captioned) plus an ``(a)`` caption line."""
        state = self._begin_subfigure()
        try:
            body = self._convert_nodes(node.nodelist)
        finally:
            self._in_subfigure = False
        return self._finish_subfigure(body, state)

    def _convert_subfloat(self, node: LatexMacroNode) -> str:
        """``\\subfloat[caption]{content}`` from the subfig package."""
        state = self._begin_subfigure()
        args = node.nodeargd.argnlist if node.nodeargd else []
        # argspec "[[{": with one [..] it's the caption; with two, the
        # first is the list-of-figures entry and the second the caption
        options = [a for a in args[:2] if a is not None]
        caption_arg = options[-1] if options else None
        try:
            if caption_arg is not None:
                self._figure_caption = self._convert_nodes(_ensure_nodelist(caption_arg)).strip()
            body = self._get_macro_arg(node)
        finally:
            self._in_subfigure = False
        return self._finish_subfigure(body, state)

    def _begin_subfigure(self) -> tuple[str, tuple[str, str, str] | None, str]:
        """Start a sub-figure; labels inside it refer to e.g. ``1a``.

        The parent figure's number is only assigned when its own \\caption
        runs (usually after the sub-figures), so predict the next number.
        """
        self._subfigure_counter += 1
        letter = chr(ord("a") + (self._subfigure_counter - 1) % 26)
        state = (self._figure_caption, self._label_target, letter)
        self._figure_caption = ""
        self._in_subfigure = True
        self._label_target = ("Figure", f"{self._figure_counter + 1}{letter}", "")
        return state

    def _finish_subfigure(
        self, body: str, state: tuple[str, tuple[str, str, str] | None, str]
    ) -> str:
        outer_caption, outer_target, letter = state
        caption = self._figure_caption
        self._figure_caption = outer_caption
        self._label_target = outer_target
        label = f"({letter}) {caption}".strip()
        if "![](" in body:
            body = body.replace("![](", f"![{label}](", 1)
        return f"\n\n{body.strip()}\n\n*{label}*\n\n"

    def _convert_table(self, node: LatexEnvironmentNode) -> str:
        outer, self._in_table = self._in_table, True
        try:
            body = self._convert_nodes(node.nodelist)
        finally:
            self._in_table = outer
        return f"\n\n{body.strip()}\n\n"

    def _convert_blockquote(self, node: LatexEnvironmentNode) -> str:
        body = self._convert_nodes(node.nodelist).strip()
        return _blockquote(body)

    # -- Theorems, proofs, beamer --

    def _register_theorem(self, node: LatexMacroNode) -> None:
        """Handle ``\\newtheorem{name}[shared]{Title}[within]`` and ``\\newtheorem*``."""
        args = node.nodeargd.argnlist if node.nodeargd else []
        # argspec "*{[{[": star, name, shared counter, title, within
        name = _extract_raw_text(args[1]).strip() if len(args) > 1 and args[1] else ""
        shared = _extract_raw_text(args[2]).strip() if len(args) > 2 and args[2] else ""
        title = _extract_raw_text(args[3]).strip() if len(args) > 3 and args[3] else ""
        if not name:
            return
        self._theorem_names[name] = title or name.capitalize()
        if args and args[0]:  # \newtheorem* -> unnumbered
            self._theorem_counter_owner[name] = ""
        elif shared:
            self._theorem_counter_owner[name] = shared

    def _convert_theorem(self, node: LatexEnvironmentNode) -> str:
        env = node.environmentname
        name = env.rstrip("*")
        title = self._theorem_names[name]
        note, nodes = self._take_env_note(node)

        owner = self._theorem_counter_owner.get(name, name)
        number = ""
        if owner and not env.endswith("*"):
            self._theorem_counters[owner] = self._theorem_counters.get(owner, 0) + 1
            number = str(self._theorem_counters[owner])
            self._set_label_target(title, number, note)

        heading = " ".join(p for p in (title, number) if p)
        if note:
            heading += f" ({note})"
        body = self._convert_nodes(nodes).strip()
        return _blockquote(f"**{heading}.** {body}")

    def _convert_proof(self, node: LatexEnvironmentNode) -> str:
        note, nodes = self._take_env_note(node)
        label = note or "Proof"
        body = self._convert_nodes(nodes).strip()
        if not body.endswith("∎"):
            body += " ∎"
        return _blockquote(f"*{label}.* {body}")

    def _frame_heading(self, title: str) -> str:
        if not title:
            return ""
        level = "###" if self._seen_section else "##"
        return f"\n\n{level} {title}\n\n"

    def _convert_frame(self, node: LatexEnvironmentNode) -> str:
        """A beamer slide: optional ``{title}{subtitle}`` groups, then content."""
        nodes = list(node.nodelist or [])
        # Drop leading whitespace and [options] (e.g. [fragile])
        while nodes and isinstance(nodes[0], LatexCharsNode):
            stripped = re.sub(r"^\s*(?:\[[^\]]*\])?\s*", "", nodes[0].chars)
            if stripped:
                nodes[0] = copy.copy(nodes[0])
                nodes[0].chars = stripped
                break
            nodes.pop(0)
        parts: list[str] = []
        if nodes and isinstance(nodes[0], LatexGroupNode):
            parts.append(self._frame_heading(self._convert_nodes(nodes.pop(0).nodelist).strip()))
            if nodes and isinstance(nodes[0], LatexGroupNode):
                subtitle = self._convert_nodes(nodes.pop(0).nodelist).strip()
                if subtitle:
                    parts.append(f"*{subtitle}*\n\n")
        parts.append(self._convert_nodes(nodes))
        return "".join(parts) + "\n\n"

    def _get_env_arg(self, node: LatexEnvironmentNode) -> str:
        """First required argument of an environment (e.g. a block title)."""
        args = node.nodeargd.argnlist if node.nodeargd else []
        for arg in args:
            if arg is not None and getattr(arg, "delimiters", ("{",))[0] == "{":
                return self._convert_nodes(_ensure_nodelist(arg)).strip()
        return ""

    def _get_required_args_raw(self, node: LatexMacroNode) -> list[str]:
        """Verbatim LaTeX of a macro's ``{...}`` arguments, skipping ``[...]`` options."""
        if not node.nodeargd or not node.nodeargd.argnlist:
            return []
        return [
            _arg_verbatim(arg)
            for arg in node.nodeargd.argnlist
            if arg is not None and getattr(arg, "delimiters", ("{",))[0] == "{"
        ]

    def _get_macro_arg_verbatim(self, node: LatexMacroNode) -> str:
        """Verbatim LaTeX of the main argument (keeps macros like ``\\metre``)."""
        arg = self._find_macro_arg(node)
        return _arg_verbatim(arg) if arg is not None else ""

    def _take_env_note(self, node: LatexEnvironmentNode) -> tuple[str, list]:
        """Return an environment's ``[note]`` and its body nodes (note removed).

        Known environments (theorem, proof, ...) get the note parsed as an
        argument; custom ones leave it as leading ``[...]`` text.
        """
        nodes = list(node.nodelist or [])
        for arg in node.nodeargd.argnlist if node.nodeargd else []:
            if arg is not None and getattr(arg, "delimiters", ("",))[0] == "[":
                return self._convert_nodes(_ensure_nodelist(arg)).strip(), nodes
        if nodes and isinstance(nodes[0], LatexCharsNode):
            match = re.match(r"\s*\[([^\]]*)\]", nodes[0].chars)
            if match:
                nodes[0] = copy.copy(nodes[0])
                nodes[0].chars = nodes[0].chars[match.end() :]
                return apply_ligatures(match.group(1)), nodes
        return "", nodes

    def _convert_block(self, node: LatexEnvironmentNode) -> str:
        """Beamer ``block``/``alertblock``/``exampleblock`` → titled blockquote."""
        title = self._get_env_arg(node)
        body = self._convert_nodes(node.nodelist).strip()
        return _blockquote(f"**{title}**\n\n{body}" if title else body)

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


def _arg_verbatim(arg) -> str:
    """Verbatim LaTeX of an argument node without its outer braces."""
    text = arg.latex_verbatim() if hasattr(arg, "latex_verbatim") else _extract_raw_text(arg)
    text = text.strip()
    if text.startswith("{") and text.endswith("}"):
        text = text[1:-1]
    return text


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
        + r"\}(?:\[[^\]]*\])*(?:\{[^}]*\})*\s*(.*?)\s*\\end\{"
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


_MULTICOLUMN_PATTERN = re.compile(r"\\multicolumn\s*\{(\d+)\}\s*\{[^}]*\}\s*\{(.*)\}", re.DOTALL)


def _split_cells(row: str) -> list[str]:
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


def _blockquote(text: str) -> str:
    """Render ``text`` as a Markdown blockquote block."""
    lines = text.strip().split("\n")
    return "\n\n" + "\n".join(f"> {line}" if line.strip() else ">" for line in lines) + "\n\n"


def _strip_math_labels(math: str) -> str:
    """Remove ``\\label{...}``, ``\\nonumber`` and ``\\notag`` from math source."""
    math = re.sub(r"\\label\s*\{[^}]*\}", "", math)
    return re.sub(r"\\(?:nonumber|notag)\b", "", math)
