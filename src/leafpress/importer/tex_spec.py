"""What the LaTeX importer knows about LaTeX: macro and environment tables.

Argument specs pylatexenc lacks, which macros are headings, formatting, or
skipped, which environments are math, and the patterns used while
converting. Kept apart from the converter so its logic reads on its own.
"""

from __future__ import annotations

import copy
import re

from pylatexenc.macrospec import EnvironmentSpec, LatexContextDb, MacroSpec

# LaTeX macros missing (or missing arguments) in pylatexenc's default
# database. Registered ahead of the defaults so these argument specs win.
EXTRA_MACROS = [
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

EXTRA_ENVIRONMENTS = [
    EnvironmentSpec("subfigure", "[{"),
    EnvironmentSpec("block", "{"),
    EnvironmentSpec("alertblock", "{"),
    EnvironmentSpec("exampleblock", "{"),
    EnvironmentSpec("column", "[{"),
    EnvironmentSpec("columns", "["),
]

# Theorem-like environments recognized without a \newtheorem declaration
DEFAULT_THEOREMS: dict[str, str] = {
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

REF_MACROS = {"ref", "eqref", "autoref", "cref", "Cref", "nameref", "pageref"}

# Beamer overlay specs (<2->, <+->) after these commands, and [<+->] list options
OVERLAY_SPEC_PATTERN = re.compile(
    r"(\\(?:item|only|visible|uncover|onslide|invisible|alert|pause|action|"
    r"textbf|textit|emph|includegraphics|color|structure|"
    r"begin\{(?:itemize|enumerate|description|block|alertblock|exampleblock|frame)\}))"
    r"\s*<[^<>\n]*>"
)
LIST_OVERLAY_OPTION_PATTERN = re.compile(
    r"(\\begin\{(?:itemize|enumerate|description)\})\s*\[<[^\]]*>\]"
)

# Placeholder for cross-references, resolved after the whole document is seen
REF_PLACEHOLDER = re.compile("\x00REF:(\\w+):([^\x00]*)\x00")

MULTIROW_MATH_ENVS = {"align", "gather", "eqnarray", "flalign"}
SINGLE_ROW_NUMBERED_ENVS = {"equation", "multline"}

HEADING_MACROS: dict[str, int] = {
    "chapter": 1,
    "section": 2,
    "subsection": 3,
    "subsubsection": 4,
    "paragraph": 5,
    "subparagraph": 6,
}

FORMAT_MACROS: dict[str, tuple[str, str]] = {
    "textbf": ("**", "**"),
    "textit": ("*", "*"),
    "emph": ("*", "*"),
    "texttt": ("`", "`"),
    "underline": ("<u>", "</u>"),
    "textsc": ("", ""),
}

SKIP_MACROS: set[str] = {
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

DEFINITION_MACROS: set[str] = {
    "newcommand",
    "renewcommand",
    "providecommand",
    "def",
    "let",
    "newenvironment",
    "renewenvironment",
}

MATH_ENVS: set[str] = {
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

SKIP_ENVS: set[str] = {
    "tikzpicture",
    "pgfpicture",
    "frame",
}

IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".svg", ".gif", ".bmp", ".webp"]
UNSUPPORTED_IMAGE_EXTENSIONS = {".pdf", ".eps", ".ps"}

# Pre-compiled patterns for code block language detection
LSTLISTING_LANG_RE = re.compile(r"\[.*?language\s*=\s*(\w+)")
MINTED_LANG_RE = re.compile(r"\\begin\{minted\}(?:\[.*?\])?\{(\w+)\}")

# Module-level cached latex context (built once, never mutated after init)
_LATEX_CONTEXT: LatexContextDb | None = None


def get_latex_context() -> LatexContextDb:
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
            macros=EXTRA_MACROS,
            environments=EXTRA_ENVIRONMENTS,
            prepend=True,
        )
        _LATEX_CONTEXT = ctx
    return _LATEX_CONTEXT
