"""LaTeX to Markdown import converter."""

from __future__ import annotations

import copy
import re
from collections.abc import Callable
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
from leafpress.importer.tex_nodes import (
    MULTICOLUMN_PATTERN,
    arg_verbatim,
    blockquote,
    ensure_nodelist,
    extract_env_body_raw,
    extract_raw_text,
    parse_column_alignments,
    split_cells,
    strip_math_labels,
)
from leafpress.importer.tex_spec import (
    DEFAULT_THEOREMS,
    DEFINITION_MACROS,
    FORMAT_MACROS,
    HEADING_MACROS,
    IMAGE_EXTENSIONS,
    LIST_OVERLAY_OPTION_PATTERN,
    LSTLISTING_LANG_RE,
    MATH_ENVS,
    MINTED_LANG_RE,
    MULTIROW_MATH_ENVS,
    OVERLAY_SPEC_PATTERN,
    REF_MACROS,
    REF_PLACEHOLDER,
    SINGLE_ROW_NUMBERED_ENVS,
    SKIP_ENVS,
    SKIP_MACROS,
    UNSUPPORTED_IMAGE_EXTENSIONS,
    get_latex_context,
)
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
        self._theorem_names: dict[str, str] = dict(DEFAULT_THEOREMS)
        self._theorem_counter_owner: dict[str, str] = {}
        self._theorem_counters: dict[str, int] = {}
        # label key -> (kind, number, title); kind is a display name like "Section"
        self._labels: dict[str, tuple[str, str, str]] = {}
        # What a \label right now would refer to
        self._label_target: tuple[str, str, str] | None = None
        self._seen_section = False
        self._warned_multicolumn = False
        self._macro_handlers = self._build_macro_handlers()

    @property
    def warnings(self) -> list[str]:
        return [*self.include_warnings, *self._warnings]

    def convert(self, latex_content: str) -> str:
        latex_content = LIST_OVERLAY_OPTION_PATTERN.sub(r"\1", latex_content)
        latex_content = OVERLAY_SPEC_PATTERN.sub(r"\1", latex_content)
        self._has_chapters = "\\chapter" in latex_content

        ctx = get_latex_context()
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
        walker = LatexWalker(latex, latex_context=get_latex_context(), tolerant_parsing=True)
        nodes, _pos, _ln = walker.get_latex_nodes()
        return self._convert_nodes(nodes)

    # -- Math --

    def _convert_math(self, node: LatexMathNode) -> str:
        raw = strip_math_labels(node.latex_verbatim())
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

        result = REF_PLACEHOLDER.sub(replace, text)
        if unresolved:
            self._warnings.append(
                "Unresolved references (shown as [ref:key]): " + ", ".join(sorted(unresolved))
            )
        return result

    # -- Macros --

    def _convert_macro(self, node: LatexMacroNode) -> str:
        name = node.macroname

        if name in HEADING_MACROS:
            return self._convert_heading(node)
        if name in FORMAT_MACROS:
            return self._convert_formatting(node)
        if name in ACCENT_MARKS and node.nodeargd and node.nodeargd.argnlist:
            return apply_accent(name, self._get_macro_arg(node))
        if name in SYMBOL_MACROS:
            return SYMBOL_MACROS[name]

        handler = self._macro_handlers.get(name)
        if handler is not None:
            return handler(node)

        if name in SKIP_MACROS:
            return ""

        if name in DEFINITION_MACROS:
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

    def _build_macro_handlers(self) -> dict[str, Callable[[LatexMacroNode], str]]:
        """Macro name -> handler for every macro with its own conversion.

        Headings, formatting, accents, and symbols are table-driven and
        checked first in ``_convert_macro``; names here never overlap them.
        """
        arg = self._get_macro_arg

        def skip(_node: LatexMacroNode) -> str:
            return ""

        def keep_content(node: LatexMacroNode) -> str:
            return arg(node)

        handlers: dict[str, Callable[[LatexMacroNode], str]] = {
            "href": self._convert_href,
            "url": self._convert_url,
            "includegraphics": self._convert_includegraphics,
            # Metadata may appear in the preamble, so it uses raw text
            "title": self._set_title,
            "author": self._set_author,
            "date": self._set_date,
            "maketitle": lambda _node: self._emit_title_block(),
            "titlepage": lambda _node: self._emit_title_block(),
            # Cross-references and citations
            "label": self._convert_label,
            **dict.fromkeys(REF_MACROS, self._convert_ref),
            **dict.fromkeys(("cite", "citep", "citet", "citeyear"), self._convert_cite),
            "footnote": self._convert_footnote,
            "item": self._convert_item,
            "caption": self._convert_caption,
            "subcaption": self._convert_subcaption,
            "\\": lambda _node: "\n",
            # Outside a tabular (handled there) just keep the content
            "multicolumn": keep_content,
            "subfloat": self._convert_subfloat,
            "texorpdfstring": lambda node: arg(node, 0),
            "textsuperscript": lambda node: f"<sup>{arg(node)}</sup>",
            "textsubscript": lambda node: f"<sub>{arg(node)}</sub>",
            "qed": lambda _node: " ∎",
            "qedsymbol": lambda _node: " ∎",
            "newtheorem": self._convert_newtheorem,
            # Beamer: overlays show everything; theme commands do nothing
            **dict.fromkeys(("only", "visible", "uncover", "onslide"), keep_content),
            **dict.fromkeys(
                ("invisible", "pause", "qedhere", "theoremstyle", "usetheme", "usecolortheme"),
                skip,
            ),
            "alert": lambda node: f"**{arg(node)}**",
            "note": self._convert_note,
            "frametitle": lambda node: self._frame_heading(arg(node).strip()),
            "framesubtitle": lambda node: f"*{arg(node).strip()}*\n\n",
            # siunitx
            **dict.fromkeys(("SI", "qty"), self._convert_si_quantity),
            **dict.fromkeys(("si", "unit"), self._convert_si_unit),
            "num": lambda node: format_si_number(self._get_macro_arg_verbatim(node)),
            "ang": lambda node: format_si_number(self._get_macro_arg_verbatim(node)) + "°",
            **dict.fromkeys(("SIrange", "qtyrange", "numrange"), self._convert_si_range),
        }
        return handlers

    def _set_title(self, node: LatexMacroNode) -> str:
        self._title = self._get_macro_arg_raw(node)
        return ""

    def _set_author(self, node: LatexMacroNode) -> str:
        self._author = self._get_macro_arg_raw(node)
        return ""

    def _set_date(self, node: LatexMacroNode) -> str:
        self._date = self._get_macro_arg_raw(node)
        return ""

    def _convert_label(self, node: LatexMacroNode) -> str:
        self._record_label(self._get_macro_arg_raw(node).strip())
        return ""

    def _convert_ref(self, node: LatexMacroNode) -> str:
        return self._ref_placeholder(node.macroname, node)

    def _convert_cite(self, node: LatexMacroNode) -> str:
        return f"[{self._get_macro_arg_raw(node)}]"

    def _convert_subcaption(self, node: LatexMacroNode) -> str:
        self._figure_caption = self._get_macro_arg(node)
        return ""

    def _convert_newtheorem(self, node: LatexMacroNode) -> str:
        self._register_theorem(node)
        return ""

    def _convert_note(self, node: LatexMacroNode) -> str:
        text = self._get_macro_arg(node).strip()
        return f"\n\n> **Note:** {text}\n\n" if text else ""

    def _convert_si_quantity(self, node: LatexMacroNode) -> str:
        args = self._get_required_args_raw(node)
        return format_si_quantity(args[0], args[-1]) if len(args) >= 2 else ""

    def _convert_si_unit(self, node: LatexMacroNode) -> str:
        return format_si_unit(self._get_macro_arg_verbatim(node))

    def _convert_si_range(self, node: LatexMacroNode) -> str:
        args = self._get_required_args_raw(node)
        if len(args) >= 2:
            return format_si_range(args[0], args[1], args[2] if len(args) > 2 else "")
        return ""

    def _convert_heading(self, node: LatexMacroNode) -> str:
        level = HEADING_MACROS[node.macroname]
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
        pre, suf = FORMAT_MACROS[node.macroname]
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

        if image_path.suffix.lower() in UNSUPPORTED_IMAGE_EXTENSIONS:
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
            candidates += [path.with_suffix(ext) for ext in IMAGE_EXTENSIONS]
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

        if name in MATH_ENVS:
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

        if name in SKIP_ENVS:
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
        inner = extract_env_body_raw(node.latex_verbatim(), name)

        if base in MULTIROW_MATH_ENVS:
            rows = re.split(r"\\\\", inner)
            if numbered:
                rows = [self._number_math_row(row) for row in rows]
                body = "\\\\".join(rows).strip()
                return f"\n\n$$\n\\begin{{{base}}}\n{body}\n\\end{{{base}}}\n$$\n\n"
            wrapper = "gathered" if base == "gather" else "aligned"
            body = "\\\\".join(strip_math_labels(r) for r in rows).strip()
            return f"\n\n$$\n\\begin{{{wrapper}}}\n{body}\n\\end{{{wrapper}}}\n$$\n\n"

        if numbered and base in SINGLE_ROW_NUMBERED_ENVS:
            body = self._number_math_row(inner).strip()
            return f"\n\n$${body}$$\n\n"
        return f"\n\n$${strip_math_labels(inner).strip()}$$\n\n"

    def _number_math_row(self, row: str) -> str:
        """Tag one numbered equation row and record any \\label on it."""
        if not row.strip() or re.search(r"\\(?:nonumber|notag)\b", row):
            return strip_math_labels(row)
        self._equation_counter += 1
        number = str(self._equation_counter)
        for key in re.findall(r"\\label\{([^}]*)\}", row):
            self._labels[key.strip()] = ("Equation", number, "")
        return f"{strip_math_labels(row).rstrip()} \\tag{{{number}}}"

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
        inner = extract_env_body_raw(raw, node.environmentname)

        lang = ""
        if node.environmentname == "lstlisting":
            match = LSTLISTING_LANG_RE.search(raw)
            if match:
                lang = match.group(1).lower()
        elif node.environmentname == "minted":
            match = MINTED_LANG_RE.match(raw)
            if match:
                lang = match.group(1).lower()

        return f"\n\n```{lang}\n{inner.strip()}\n```\n\n"

    def _convert_tabular(self, node: LatexEnvironmentNode) -> str:
        raw = node.latex_verbatim()
        inner = extract_env_body_raw(raw, node.environmentname)

        col_spec = ""
        begin_match = re.match(
            r"\\begin\{" + re.escape(node.environmentname) + r"\}\s*(?:\{[^}]*\}\s*)?\{([^}]*)\}"
            if node.environmentname in ("tabular*", "tabularx")
            else r"\\begin\{" + re.escape(node.environmentname) + r"\}\s*\{([^}]*)\}",
            raw,
        )
        if begin_match:
            col_spec = begin_match.group(1)

        alignments = parse_column_alignments(col_spec)

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
            for cell in split_cells(row_str):
                span = MULTICOLUMN_PATTERN.fullmatch(cell.strip())
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
                self._figure_caption = self._convert_nodes(ensure_nodelist(caption_arg)).strip()
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
        return blockquote(body)

    # -- Theorems, proofs, beamer --

    def _register_theorem(self, node: LatexMacroNode) -> None:
        """Handle ``\\newtheorem{name}[shared]{Title}[within]`` and ``\\newtheorem*``."""
        args = node.nodeargd.argnlist if node.nodeargd else []
        # argspec "*{[{[": star, name, shared counter, title, within
        name = extract_raw_text(args[1]).strip() if len(args) > 1 and args[1] else ""
        shared = extract_raw_text(args[2]).strip() if len(args) > 2 and args[2] else ""
        title = extract_raw_text(args[3]).strip() if len(args) > 3 and args[3] else ""
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
        return blockquote(f"**{heading}.** {body}")

    def _convert_proof(self, node: LatexEnvironmentNode) -> str:
        note, nodes = self._take_env_note(node)
        label = note or "Proof"
        body = self._convert_nodes(nodes).strip()
        if not body.endswith("∎"):
            body += " ∎"
        return blockquote(f"*{label}.* {body}")

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
                return self._convert_nodes(ensure_nodelist(arg)).strip()
        return ""

    def _get_required_args_raw(self, node: LatexMacroNode) -> list[str]:
        """Verbatim LaTeX of a macro's ``{...}`` arguments, skipping ``[...]`` options."""
        if not node.nodeargd or not node.nodeargd.argnlist:
            return []
        return [
            arg_verbatim(arg)
            for arg in node.nodeargd.argnlist
            if arg is not None and getattr(arg, "delimiters", ("{",))[0] == "{"
        ]

    def _get_macro_arg_verbatim(self, node: LatexMacroNode) -> str:
        """Verbatim LaTeX of the main argument (keeps macros like ``\\metre``)."""
        arg = self._find_macro_arg(node)
        return arg_verbatim(arg) if arg is not None else ""

    def _take_env_note(self, node: LatexEnvironmentNode) -> tuple[str, list]:
        """Return an environment's ``[note]`` and its body nodes (note removed).

        Known environments (theorem, proof, ...) get the note parsed as an
        argument; custom ones leave it as leading ``[...]`` text.
        """
        nodes = list(node.nodelist or [])
        for arg in node.nodeargd.argnlist if node.nodeargd else []:
            if arg is not None and getattr(arg, "delimiters", ("",))[0] == "[":
                return self._convert_nodes(ensure_nodelist(arg)).strip(), nodes
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
        return blockquote(f"**{title}**\n\n{body}" if title else body)

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
        return self._convert_nodes(ensure_nodelist(arg))

    def _get_macro_arg_raw(self, node: LatexMacroNode, index: int = -1) -> str:
        """Get the raw text of a macro's argument (not recursively converted)."""
        arg = self._find_macro_arg(node, index)
        if arg is None:
            return ""
        return extract_raw_text(arg)

    def _get_all_macro_args(self, node: LatexMacroNode) -> list[str]:
        """Get all non-None macro arguments as converted strings."""
        if not node.nodeargd or not node.nodeargd.argnlist:
            return []
        return [
            self._convert_nodes(ensure_nodelist(arg))
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
                    return self._convert_nodes(ensure_nodelist(arg))
        return ""


# -- Module-level helpers --
