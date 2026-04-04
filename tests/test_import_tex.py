"""Tests for LaTeX to Markdown import."""

from pathlib import Path

import pytest
from helpers import make_png
from typer.testing import CliRunner

from leafpress.cli import cli
from leafpress.exceptions import TexImportError
from leafpress.importer.converter_tex import import_tex

runner = CliRunner()

SAMPLE_TEX = r"""\documentclass{article}
\usepackage{graphicx}
\usepackage{hyperref}
\usepackage{amsmath}
\usepackage{listings}

\title{Test Document}
\author{Test Author}
\date{2024-01-15}

\begin{document}
\maketitle

\section{Introduction}
Hello \textbf{bold text} and \textit{italic text} and \texttt{code text}.

\subsection{Sub Heading}
Some content here.

\section{Lists}

\begin{itemize}
\item First item
\item Second item
\end{itemize}

\begin{enumerate}
\item Numbered one
\item Numbered two
\end{enumerate}

\section{Math}

Inline: $E = mc^2$.

\begin{equation}
\int_0^\infty e^{-x} dx = 1
\end{equation}

\section{Tables}

\begin{tabular}{|l|r|}
\hline
Header 1 & Header 2 \\
\hline
Cell A & Cell B \\
\hline
\end{tabular}

\section{Links}

Visit \href{https://example.com}{Example Site} or \url{https://example.com/docs}.

\section{Code}

\begin{verbatim}
print("hello")
\end{verbatim}

\section{Blockquote}

\begin{quote}
A quoted passage.
\end{quote}

This has a footnote\footnote{Footnote content here.} in it.

\end{document}
"""


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_tex(tmp_path: Path) -> Path:
    path = tmp_path / "test.tex"
    path.write_text(SAMPLE_TEX, encoding="utf-8")
    return path


@pytest.fixture
def academic_paper(tmp_path: Path) -> Path:
    """Copy the academic paper fixture into a tmp dir so output is isolated."""
    src = FIXTURES_DIR / "academic_paper.tex"
    dest = tmp_path / "academic_paper.tex"
    dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return dest


def test_import_basic(sample_tex: Path, tmp_output: Path) -> None:
    """End-to-end: .tex in, .md out, file exists with content."""
    result = import_tex(sample_tex, output_path=tmp_output)
    assert result.markdown_path.exists()
    assert result.markdown_path.suffix == ".md"
    content = result.markdown_path.read_text()
    assert len(content) > 0
    assert "Test Document" in content


def test_import_headings(sample_tex: Path, tmp_output: Path) -> None:
    """Section commands converted to ATX-style markdown headings."""
    result = import_tex(sample_tex, output_path=tmp_output)
    content = result.markdown_path.read_text()
    assert "## Introduction" in content
    assert "### Sub Heading" in content
    assert "## Lists" in content


def test_import_title_block(sample_tex: Path, tmp_output: Path) -> None:
    """Title, author, and date rendered at top."""
    result = import_tex(sample_tex, output_path=tmp_output)
    content = result.markdown_path.read_text()
    assert "# Test Document" in content
    assert "Test Author" in content
    assert "2024-01-15" in content


def test_import_formatting(sample_tex: Path, tmp_output: Path) -> None:
    """Bold, italic, and code formatting preserved."""
    result = import_tex(sample_tex, output_path=tmp_output)
    content = result.markdown_path.read_text()
    assert "**bold text**" in content
    assert "*italic text*" in content
    assert "`code text`" in content


def test_import_lists(sample_tex: Path, tmp_output: Path) -> None:
    """Bullet and numbered lists present in output."""
    result = import_tex(sample_tex, output_path=tmp_output)
    content = result.markdown_path.read_text()
    assert "First item" in content
    assert "Second item" in content
    assert "Numbered one" in content
    assert "Numbered two" in content


def test_import_bullet_list_markers(sample_tex: Path, tmp_output: Path) -> None:
    """Bullet list items have - markers."""
    result = import_tex(sample_tex, output_path=tmp_output)
    content = result.markdown_path.read_text()
    assert "- First item" in content
    assert "- Second item" in content


def test_import_numbered_list_markers(sample_tex: Path, tmp_output: Path) -> None:
    """Numbered list items have 1. 2. markers."""
    result = import_tex(sample_tex, output_path=tmp_output)
    content = result.markdown_path.read_text()
    assert "1. Numbered one" in content
    assert "2. Numbered two" in content


def test_import_nested_lists(tmp_path: Path, tmp_output: Path) -> None:
    """Nested lists produce indented output."""
    tex = r"""\documentclass{article}
\begin{document}
\begin{itemize}
\item Outer
  \begin{itemize}
  \item Inner
  \end{itemize}
\end{itemize}
\end{document}
"""
    path = tmp_path / "nested.tex"
    path.write_text(tex, encoding="utf-8")
    result = import_tex(path, output_path=tmp_output)
    content = result.markdown_path.read_text()
    assert "- Outer" in content
    assert "  - Inner" in content


def test_import_math_inline(sample_tex: Path, tmp_output: Path) -> None:
    """Inline math passed through verbatim."""
    result = import_tex(sample_tex, output_path=tmp_output)
    content = result.markdown_path.read_text()
    assert "$E = mc^2$" in content


def test_import_math_display(sample_tex: Path, tmp_output: Path) -> None:
    """Display math wrapped in $$."""
    result = import_tex(sample_tex, output_path=tmp_output)
    content = result.markdown_path.read_text()
    assert "$$" in content
    assert "\\int_0^\\infty" in content


def test_import_tables(sample_tex: Path, tmp_output: Path) -> None:
    """Tables converted to pipe-style markdown."""
    result = import_tex(sample_tex, output_path=tmp_output)
    content = result.markdown_path.read_text()
    assert "Header 1" in content
    assert "Header 2" in content
    assert "Cell A" in content
    assert "Cell B" in content
    assert "---" in content


def test_import_links(sample_tex: Path, tmp_output: Path) -> None:
    """Hyperlinks converted to markdown link syntax."""
    result = import_tex(sample_tex, output_path=tmp_output)
    content = result.markdown_path.read_text()
    assert "[Example Site](https://example.com)" in content
    assert "<https://example.com/docs>" in content


def test_import_verbatim(sample_tex: Path, tmp_output: Path) -> None:
    """Verbatim environment converted to fenced code block."""
    result = import_tex(sample_tex, output_path=tmp_output)
    content = result.markdown_path.read_text()
    assert "```" in content
    assert 'print("hello")' in content


def test_import_blockquote(sample_tex: Path, tmp_output: Path) -> None:
    """Quote environment converted to blockquote."""
    result = import_tex(sample_tex, output_path=tmp_output)
    content = result.markdown_path.read_text()
    assert "> A quoted passage." in content


def test_import_footnotes(sample_tex: Path, tmp_output: Path) -> None:
    """Footnotes converted to markdown footnote syntax."""
    result = import_tex(sample_tex, output_path=tmp_output)
    content = result.markdown_path.read_text()
    assert "[^1]" in content
    assert "[^1]: Footnote content here." in content


def test_import_preamble_stripped(sample_tex: Path, tmp_output: Path) -> None:
    """Preamble commands do not appear in output."""
    result = import_tex(sample_tex, output_path=tmp_output)
    content = result.markdown_path.read_text()
    assert "\\documentclass" not in content
    assert "\\usepackage" not in content


def test_import_custom_macros_warned(tmp_path: Path, tmp_output: Path) -> None:
    """Custom macro definitions produce warnings."""
    tex = r"""\documentclass{article}
\newcommand{\foo}{bar}
\begin{document}
Hello.
\end{document}
"""
    path = tmp_path / "macros.tex"
    path.write_text(tex, encoding="utf-8")
    result = import_tex(path, output_path=tmp_output)
    assert any("newcommand" in w for w in result.warnings)


def test_import_images(tmp_path: Path, tmp_output: Path) -> None:
    """Images copied to assets/ and referenced in markdown."""
    img_path = tmp_path / "figure.png"
    img_path.write_bytes(make_png())

    tex = r"""\documentclass{article}
\usepackage{graphicx}
\begin{document}
\includegraphics{figure.png}
\end{document}
"""
    tex_path = tmp_path / "test.tex"
    tex_path.write_text(tex, encoding="utf-8")
    result = import_tex(tex_path, output_path=tmp_output)
    content = result.markdown_path.read_text()
    assert "![](assets/" in content
    assert len(result.images) == 1


def test_import_images_not_extracted(tmp_path: Path, tmp_output: Path) -> None:
    """With extract_images=False, no images are copied."""
    tex = r"""\documentclass{article}
\begin{document}
\includegraphics{missing.png}
\end{document}
"""
    tex_path = tmp_path / "test.tex"
    tex_path.write_text(tex, encoding="utf-8")
    result = import_tex(tex_path, output_path=tmp_output, extract_images=False)
    assert len(result.images) == 0


def test_import_output_dir(sample_tex: Path, tmp_output: Path) -> None:
    """Output to directory creates stem.md inside it."""
    result = import_tex(sample_tex, output_path=tmp_output)
    assert result.markdown_path == tmp_output / "test.md"


def test_import_output_file(sample_tex: Path, tmp_path: Path) -> None:
    """Output to specific .md file path."""
    out_file = tmp_path / "custom.md"
    result = import_tex(sample_tex, output_path=out_file)
    assert result.markdown_path == out_file
    assert out_file.exists()


def test_import_default_output(sample_tex: Path) -> None:
    """No output path writes sibling .md file."""
    result = import_tex(sample_tex)
    assert result.markdown_path == sample_tex.with_suffix(".md")
    assert result.markdown_path.exists()


def test_import_nonexistent_file(tmp_path: Path) -> None:
    """Missing file raises TexImportError."""
    with pytest.raises(TexImportError, match="File not found"):
        import_tex(tmp_path / "nonexistent.tex")


def test_import_non_tex_file(tmp_path: Path) -> None:
    """Wrong extension raises TexImportError."""
    path = tmp_path / "test.txt"
    path.write_text("hello")
    with pytest.raises(TexImportError, match=r"Not a \.tex file"):
        import_tex(path)


def test_import_no_document_env(tmp_path: Path, tmp_output: Path) -> None:
    """LaTeX snippet without \\begin{document} is treated as body."""
    tex = r"""
\section{Hello}
This is a snippet.
"""
    path = tmp_path / "snippet.tex"
    path.write_text(tex, encoding="utf-8")
    result = import_tex(path, output_path=tmp_output)
    content = result.markdown_path.read_text()
    assert "## Hello" in content
    assert "snippet" in content


def test_import_cli(sample_tex: Path, tmp_output: Path) -> None:
    """CLI end-to-end test."""
    result = runner.invoke(cli, ["import", str(sample_tex), "-o", str(tmp_output)])
    assert result.exit_code == 0


def test_import_cli_nonexistent(tmp_path: Path) -> None:
    """CLI exits 1 for missing file."""
    result = runner.invoke(cli, ["import", str(tmp_path / "missing.tex")])
    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# Academic paper fixture tests — exercises features not covered by sample_tex
# ---------------------------------------------------------------------------


class TestAcademicPaper:
    """Tests using the academic_paper.tex fixture (realistic research paper)."""

    @pytest.fixture(autouse=True)
    def _convert(self, academic_paper: Path, tmp_output: Path) -> None:
        self.result = import_tex(academic_paper, output_path=tmp_output)
        self.content = self.result.markdown_path.read_text()

    def test_converts_successfully(self) -> None:
        """Full paper converts without crashing."""
        assert self.result.markdown_path.exists()
        assert len(self.content) > 500

    def test_title_block(self) -> None:
        """Title, author, date rendered."""
        assert "Convergence Properties" in self.content
        assert "Alice Researcher" in self.content
        assert "March 2024" in self.content

    def test_abstract_as_blockquote(self) -> None:
        """Abstract environment rendered as blockquote."""
        assert "> " in self.content
        assert "convergence behavior" in self.content

    def test_sections_and_subsections(self) -> None:
        """Section hierarchy preserved."""
        assert "## Introduction" in self.content
        assert "## Theoretical Framework" in self.content
        assert "### Assumptions" in self.content
        assert "### Main Result" in self.content
        assert "## Experiments" in self.content
        assert "## Conclusion" in self.content

    def test_paragraph_headings(self) -> None:
        """\\paragraph content present in output."""
        assert "Contributions" in self.content
        assert "Notation" in self.content

    def test_description_list(self) -> None:
        """Description list items rendered with bold labels."""
        assert "**Convex optimization**" in self.content
        assert "**Non-convex optimization**" in self.content
        assert "**Stochastic methods**" in self.content

    def test_numbered_list(self) -> None:
        """Numbered lists with correct markers."""
        assert "1." in self.content
        assert "2." in self.content
        assert "3." in self.content

    def test_nested_bullet_list(self) -> None:
        """Nested itemize produces indented bullets."""
        assert "  - Nesterov variant" in self.content
        assert "  - Warmup period" in self.content

    def test_inline_math(self) -> None:
        """Inline math passed through verbatim."""
        assert "$\\mathcal{O}(1/\\sqrt{T})$" in self.content
        assert "$\\mathcal{L}$" in self.content

    def test_labeled_equation(self) -> None:
        """Labeled equation environment wrapped in $$."""
        assert "$$" in self.content
        assert "\\arg\\min" in self.content

    def test_align_environment(self) -> None:
        """align environment wrapped in $$."""
        assert "\\nabla \\mathcal{L}" in self.content

    def test_equation_star(self) -> None:
        """equation* (unnumbered) wrapped in $$."""
        assert "\\sqrt{" in self.content

    def test_citations(self) -> None:
        """\\cite and \\citet produce bracketed references."""
        assert "[bottou2018]" in self.content
        assert "[allen2019]" in self.content

    def test_cross_references(self) -> None:
        """\\ref and \\eqref produce ref markers."""
        assert "[ref:sec:theory]" in self.content
        assert "[ref:tab:comparison]" in self.content

    def test_table_with_booktabs(self) -> None:
        """Tables with \\toprule/\\midrule/\\bottomrule still convert."""
        assert "Method" in self.content
        assert "Rate" in self.content
        assert "---" in self.content

    def test_table_with_hline(self) -> None:
        """Standard \\hline table converts to pipe table."""
        assert "Dataset" in self.content
        assert "MNIST" in self.content
        assert "CIFAR-10" in self.content

    def test_figure_warning(self) -> None:
        """Missing image produces a warning."""
        assert any("convergence_plot" in w for w in self.result.warnings)

    def test_figure_caption(self) -> None:
        """Figure caption incorporated into image alt text."""
        assert "Convergence of gradient descent" in self.content

    def test_footnotes(self) -> None:
        """Multiple footnotes get unique markers."""
        assert "[^1]" in self.content
        assert "[^2]" in self.content
        assert "[^1]: " in self.content
        assert "[^2]: " in self.content

    def test_verbatim_code_block(self) -> None:
        """Verbatim block converted to fenced code."""
        assert "```" in self.content
        assert "loss.backward()" in self.content

    def test_lstlisting_with_language(self) -> None:
        """lstlisting[language=Python] gets python fence marker."""
        assert "```python" in self.content
        assert "def gradient_descent" in self.content

    def test_formatting(self) -> None:
        """Bold, italic, emph, underline, texttt, textsc."""
        assert "**Smoothness**" in self.content
        assert "*Rosenbrock function*" in self.content
        assert "`code text`" not in self.content  # no texttt in this doc
        assert "<u>non-convex settings</u>" in self.content

    def test_href_link(self) -> None:
        """\\href converted to markdown link."""
        url = "https://github.com/example/gradient-descent"
        assert f"GitHub page]({url})" in self.content

    def test_url_link(self) -> None:
        """\\url converted to angle-bracket link."""
        assert "<https://example.com/gradient-convergence>" in self.content

    def test_quote_blockquote(self) -> None:
        """quote environment as blockquote."""
        assert "> The art of optimization" in self.content

    def test_quotation_blockquote(self) -> None:
        """quotation environment as blockquote."""
        assert "> Gradient descent is remarkably" in self.content

    def test_preamble_stripped(self) -> None:
        """Preamble commands absent from output."""
        assert "\\documentclass" not in self.content
        assert "\\usepackage" not in self.content
        assert "\\bibliographystyle" not in self.content

    def test_label_stripped_from_prose(self) -> None:
        """\\label commands outside math don't appear as prose text."""
        # Labels inside math environments are preserved verbatim (expected),
        # but standalone \\label macros in prose should be stripped.
        non_math_lines = [
            line
            for line in self.content.split("\n")
            if not line.strip().startswith("$$") and "$$" not in line
        ]
        prose = "\n".join(non_math_lines)
        assert "\\label" not in prose

    def test_warnings_produced(self) -> None:
        """Converter produces warnings for missing images."""
        assert len(self.result.warnings) > 0
        assert any("Image not found" in w for w in self.result.warnings)


# ---------------------------------------------------------------------------
# Edge case and coverage gap tests
# ---------------------------------------------------------------------------


def _convert_snippet(tex: str, tmp_path: Path, tmp_output: Path, **kwargs) -> tuple[str, list[str]]:
    """Helper: write tex to file, convert, return (content, warnings)."""
    path = tmp_path / "test.tex"
    path.write_text(tex, encoding="utf-8")
    result = import_tex(path, output_path=tmp_output, **kwargs)
    return result.markdown_path.read_text(), result.warnings


class TestTexEdgeCases:
    """Tests targeting specific uncovered code paths in converter_tex.py."""

    def test_date_and_maketitle(self, tmp_path: Path, tmp_output: Path) -> None:
        """\\date and \\maketitle render title block with date."""
        tex = r"""\documentclass{article}
\title{My Paper}
\author{Jane Doe}
\date{2025-01-01}
\begin{document}
\maketitle
Hello.
\end{document}
"""
        content, _ = _convert_snippet(tex, tmp_path, tmp_output)
        assert "# My Paper" in content
        assert "Jane Doe" in content
        assert "2025-01-01" in content

    def test_maketitle_no_metadata(self, tmp_path: Path, tmp_output: Path) -> None:
        """\\maketitle with no title/author/date produces nothing."""
        tex = r"""\documentclass{article}
\begin{document}
\maketitle
Hello.
\end{document}
"""
        content, _ = _convert_snippet(tex, tmp_path, tmp_output)
        assert "Hello" in content

    def test_eqref_and_autoref(self, tmp_path: Path, tmp_output: Path) -> None:
        """\\eqref and \\autoref produce ref markers."""
        tex = r"""\documentclass{article}
\begin{document}
See equation \eqref{eq:main} and \autoref{fig:one}.
\end{document}
"""
        content, _ = _convert_snippet(tex, tmp_path, tmp_output)
        assert "[ref:eq:main]" in content
        assert "[ref:fig:one]" in content

    def test_citep_and_citeyear(self, tmp_path: Path, tmp_output: Path) -> None:
        """\\citep and \\citeyear produce bracketed keys."""
        tex = r"""\documentclass{article}
\begin{document}
Results from \citep{smith2020} published in \citeyear{smith2020}.
\end{document}
"""
        content, _ = _convert_snippet(tex, tmp_path, tmp_output)
        assert "[smith2020]" in content

    def test_unsupported_image_format(self, tmp_path: Path, tmp_output: Path) -> None:
        """EPS/PDF images produce a warning."""
        (tmp_path / "figure.eps").write_bytes(b"fake eps")
        tex = r"""\documentclass{article}
\usepackage{graphicx}
\begin{document}
\includegraphics{figure.eps}
\end{document}
"""
        _, warnings = _convert_snippet(tex, tmp_path, tmp_output)
        assert any("Unsupported image format" in w for w in warnings)

    def test_image_extension_resolution(self, tmp_path: Path, tmp_output: Path) -> None:
        """\\includegraphics without extension finds .png file."""
        (tmp_path / "diagram.png").write_bytes(make_png())
        tex = r"""\documentclass{article}
\usepackage{graphicx}
\begin{document}
\includegraphics{diagram}
\end{document}
"""
        content, _ = _convert_snippet(tex, tmp_path, tmp_output)
        assert "![](assets/" in content

    def test_skip_environment_warns(self, tmp_path: Path, tmp_output: Path) -> None:
        """tikzpicture environment is skipped with a warning."""
        tex = r"""\documentclass{article}
\begin{document}
Before.
\begin{tikzpicture}
\draw (0,0) -- (1,1);
\end{tikzpicture}
After.
\end{document}
"""
        content, warnings = _convert_snippet(tex, tmp_path, tmp_output)
        assert "Before" in content
        assert "After" in content
        assert "draw" not in content
        assert any("tikzpicture" in w for w in warnings)

    def test_unknown_environment_warns(self, tmp_path: Path, tmp_output: Path) -> None:
        """Unknown environments render body with a warning."""
        tex = r"""\documentclass{article}
\begin{document}
\begin{customenv}
Body text here.
\end{customenv}
\end{document}
"""
        content, warnings = _convert_snippet(tex, tmp_path, tmp_output)
        assert "Body text here" in content
        assert any("customenv" in w for w in warnings)

    def test_center_and_minipage_passthrough(self, tmp_path: Path, tmp_output: Path) -> None:
        """center and minipage environments pass through their content."""
        tex = r"""\documentclass{article}
\begin{document}
\begin{center}
Centered text.
\end{center}
\begin{minipage}{0.5\textwidth}
Mini content.
\end{minipage}
\end{document}
"""
        content, _ = _convert_snippet(tex, tmp_path, tmp_output)
        assert "Centered text" in content
        assert "Mini content" in content

    def test_backslash_newline(self, tmp_path: Path, tmp_output: Path) -> None:
        """Double backslash produces a newline."""
        tex = r"""\documentclass{article}
\begin{document}
Line one.\\Line two.
\end{document}
"""
        content, _ = _convert_snippet(tex, tmp_path, tmp_output)
        assert "Line one." in content
        assert "Line two." in content

    def test_unknown_macro_fallback(self, tmp_path: Path, tmp_output: Path) -> None:
        """Unknown macros render their argument and warn."""
        tex = r"""\documentclass{article}
\begin{document}
Hello \custommacro{world}.
\end{document}
"""
        content, warnings = _convert_snippet(tex, tmp_path, tmp_output)
        assert "world" in content
        assert any("custommacro" in w for w in warnings)

    def test_definition_macro_warns(self, tmp_path: Path, tmp_output: Path) -> None:
        """\\renewcommand and \\def produce warnings."""
        tex = r"""\documentclass{article}
\renewcommand{\foo}{bar}
\def\baz{qux}
\begin{document}
Hello.
\end{document}
"""
        _, warnings = _convert_snippet(tex, tmp_path, tmp_output)
        assert any("renewcommand" in w for w in warnings)
        assert any("def" in w for w in warnings)

    def test_read_failure_raises(self, tmp_path: Path, tmp_output: Path) -> None:
        """Unreadable file raises TexImportError."""
        path = tmp_path / "bad.tex"
        path.write_bytes(b"\x80\x81\x82")  # invalid UTF-8
        with pytest.raises(TexImportError, match="Failed to read"):
            import_tex(path, output_path=tmp_output)

    def test_tabular_column_alignment(self, tmp_path: Path, tmp_output: Path) -> None:
        """Table column alignment parsed from col spec."""
        tex = r"""\documentclass{article}
\begin{document}
\begin{tabular}{|l|c|r|}
Left & Center & Right \\
A & B & C \\
\end{tabular}
\end{document}
"""
        content, _ = _convert_snippet(tex, tmp_path, tmp_output)
        assert "Left" in content
        assert "---" in content
        # Check alignment markers in separator
        lines = [ln for ln in content.split("\n") if "---" in ln and "|" in ln]
        assert len(lines) >= 1
        sep = lines[0]
        assert ":" in sep  # center or right alignment marker
