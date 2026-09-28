"""Tests for LaTeX import: includes, theorems, accents, siunitx, tables, refs, beamer."""

from __future__ import annotations

from pathlib import Path

import pytest

from leafpress.importer.converter_tex import _TexToMarkdownConverter, import_tex
from leafpress.importer.tex_symbols import (
    apply_accent,
    apply_ligatures,
    format_si_number,
    format_si_quantity,
    format_si_unit,
)


def convert(latex: str) -> tuple[str, list[str]]:
    conv = _TexToMarkdownConverter(tex_dir=Path("."), image_handler=None)
    return conv.convert(latex), conv.warnings


def flat(text: str) -> str:
    return " ".join(text.split())


# ---------------------------------------------------------------------------
# \input / \include
# ---------------------------------------------------------------------------


class TestIncludes:
    def _main(self, tmp_path: Path, body: str) -> Path:
        main = tmp_path / "paper" / "main.tex"
        main.parent.mkdir(parents=True, exist_ok=True)
        main.write_text(f"\\documentclass{{article}}\\begin{{document}}\n{body}\n\\end{{document}}")
        return main

    def test_input_and_include_inlined(self, tmp_path: Path) -> None:
        main = self._main(tmp_path, "\\input{intro}\n\\include{chapters/two}")
        (main.parent / "intro.tex").write_text("\\section{Intro}Hello from intro.")
        (main.parent / "chapters").mkdir()
        (main.parent / "chapters" / "two.tex").write_text("\\section{Two}Second \\input{nested}")
        (main.parent / "nested.tex").write_text("and nested.")
        result = import_tex(main, output_path=tmp_path / "out")
        content = result.markdown_path.read_text()
        assert "## Intro" in content and "Hello from intro." in content
        assert "## Two" in content and "Second and nested." in flat(content)
        assert result.warnings == []

    def test_commented_include_ignored(self, tmp_path: Path) -> None:
        main = self._main(tmp_path, "% \\input{secret}\nVisible \\% \\input{shown}")
        (main.parent / "secret.tex").write_text("SHOULD-NOT-APPEAR")
        (main.parent / "shown.tex").write_text("shown-text")
        content = import_tex(main, output_path=tmp_path / "out").markdown_path.read_text()
        assert "SHOULD-NOT-APPEAR" not in content
        assert "shown-text" in content

    def test_outside_directory_refused(self, tmp_path: Path) -> None:
        (tmp_path / "secret.tex").write_text("TOP-SECRET")
        main = self._main(tmp_path, f"\\input{{../secret}}\\input{{{tmp_path / 'secret'}}}")
        result = import_tex(main, output_path=tmp_path / "out")
        assert "TOP-SECRET" not in result.markdown_path.read_text()
        assert sum("outside the document directory" in w for w in result.warnings) == 2

    def test_cycle_and_missing_reported(self, tmp_path: Path) -> None:
        main = self._main(tmp_path, "\\input{a}\\input{missing}\\input{main}")
        (main.parent / "a.tex").write_text("A-text \\input{b}")
        (main.parent / "b.tex").write_text("B-text \\input{a}")
        result = import_tex(main, output_path=tmp_path / "out")
        content = result.markdown_path.read_text()
        assert content.count("A-text") == 1 and content.count("B-text") == 1
        assert any("cycle" in w for w in result.warnings)
        assert any("not found: missing" in w for w in result.warnings)

    def test_subfile_uses_document_body(self, tmp_path: Path) -> None:
        main = self._main(tmp_path, "\\subfile{sec}")
        (main.parent / "sec.tex").write_text(
            "\\documentclass[main.tex]{subfiles}\\begin{document}Sub body\\end{document}"
        )
        content = import_tex(main, output_path=tmp_path / "out").markdown_path.read_text()
        assert "Sub body" in content and "subfiles" not in content

    def test_import_and_subimport(self, tmp_path: Path) -> None:
        main = self._main(tmp_path, "\\import{parts/}{p1}")
        (main.parent / "parts").mkdir()
        (main.parent / "parts" / "p1.tex").write_text("Part one \\subimport{./}{p2}")
        (main.parent / "parts" / "p2.tex").write_text("part two")
        content = import_tex(main, output_path=tmp_path / "out").markdown_path.read_text()
        assert "Part one part two" in flat(content)


# ---------------------------------------------------------------------------
# Headings, captions, accents, ligatures
# ---------------------------------------------------------------------------


def test_paragraph_heading_has_title() -> None:
    out, _ = convert("\\paragraph{Para Title} Body. \\subparagraph{Sub} More.")
    assert "##### Para Title" in out
    assert "###### Sub" in out


def test_figure_caption_is_alt_text_and_numbered() -> None:
    """Regression: \\caption had no argument spec, so captions leaked as loose text."""
    conv = _TexToMarkdownConverter(tex_dir=Path("."), image_handler=None)
    out = conv.convert("\\begin{figure}\\includegraphics{x.png}\\caption{My cap}\\end{figure}")
    assert "*Figure 1: My cap*" in out
    assert out.count("My cap") == 1  # not also leaked as a plain paragraph


@pytest.mark.parametrize(
    ("latex", "expected"),
    [
        ('Sch\\"on', "Schön"),
        ("caf\\'e", "café"),
        ("se\\~nor", "señor"),
        ("\\c{c}a", "ça"),
        ('na\\"{\\i}ve', "naïve"),
        ("\\v{s}", "š"),
        ("\\o{} \\ss{} \\ae{}", "ø ß æ"),
        ("\\& \\% \\$ \\#", "& % \\$ \\#"),
        ("a---b a--b ``q''", "a—b a–b “q”"),
        ("x~y", "x y"),
        ("\\texttt{--flag}", "`--flag`"),
        # A control word swallows the following space, as in LaTeX itself
        ("\\ldots{} \\copyright", "… ©"),
    ],
)
def test_accents_symbols_and_ligatures(latex: str, expected: str) -> None:
    out, warnings = convert(latex)
    assert out.strip() == expected
    assert not any("Unknown macro" in w for w in warnings)


def test_symbol_helpers() -> None:
    assert apply_accent('"', "u") == "ü"
    assert apply_accent("'", "") == "\u0301"
    assert apply_ligatures("--- -- ``x''") == "— – “x”"


# ---------------------------------------------------------------------------
# Theorems and proofs
# ---------------------------------------------------------------------------


def test_theorems_numbered_with_shared_counters_and_refs() -> None:
    out, warnings = convert(
        "\\newtheorem{theorem}{Theorem}\\newtheorem{lemma}[theorem]{Lemma}"
        "\\newtheorem*{remark*}{Remark}\\newtheorem{thm}{Satz}"
        "\\begin{theorem}[Pythagoras]\\label{thm:p} Body.\\end{theorem}"
        "\\begin{lemma}Small.\\end{lemma}"
        "\\begin{thm}[Note]Custom.\\end{thm}"
        "\\begin{proof}Trivial.\\end{proof}"
        "\\begin{proof}[Proof of Lemma]Done.\\qed\\end{proof}"
        "See Theorem~\\ref{thm:p} and \\autoref{thm:p}."
    )
    assert "> **Theorem 1 (Pythagoras).** Body." in out
    assert "> **Lemma 2.** Small." in out
    assert "> **Satz 1 (Note).** Custom." in out
    assert "> *Proof.* Trivial. ∎" in out
    assert "> *Proof of Lemma.* Done. ∎" in out  # no doubled ∎
    assert "See Theorem 1 and Theorem 1." in flat(out)
    assert not any("Unknown environment" in w for w in warnings)


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


def test_multicolumn_and_cell_conversion() -> None:
    out, warnings = convert(
        "\\begin{tabular}{|l|c|r|}\\hline\\multicolumn{2}{c|}{\\textbf{Span}} & X \\\\"
        "a \\& b & $x$ & \\emph{c} \\\\\\hline\\end{tabular}"
    )
    lines = out.strip().splitlines()
    assert lines[0].split("|")[1].strip() == "**Span**"
    assert "a & b" in lines[2] and "$x$" in lines[2] and "*c*" in lines[2]
    assert any("multicolumn" in w for w in warnings)


def test_table_caption_numbered_and_referenced() -> None:
    out, _ = convert(
        "\\begin{table}\\caption{Results}\\label{tab:r}\\begin{tabular}{ll}a&b\\\\"
        "\\end{tabular}\\end{table} See Table~\\ref{tab:r}."
    )
    assert "*Table 1: Results*" in out
    assert "See Table 1." in flat(out)


# ---------------------------------------------------------------------------
# Sub-figures
# ---------------------------------------------------------------------------


def test_subfigures_and_subfloat() -> None:
    out, warnings = convert(
        "\\begin{figure}"
        "\\begin{subfigure}{0.45\\textwidth}\\caption{Left}\\label{fig:l}\\end{subfigure}"
        "\\begin{subfigure}{0.45\\textwidth}\\caption{Right}\\end{subfigure}"
        "\\caption{Both}\\label{fig:both}\\end{figure}"
        "\\begin{figure}\\subfloat[Only]{X}\\caption{Second}\\end{figure}"
        "See \\ref{fig:l} of Figure~\\ref{fig:both}."
    )
    assert "*(a) Left*" in out and "*(b) Right*" in out
    assert "*Figure 1: Both*" in out
    assert "*(a) Only*" in out and "*Figure 2: Second*" in out
    assert "See 1a of Figure 1." in flat(out)
    assert "0.45" not in out  # width argument not leaked
    assert not any("subfigure" in w for w in warnings)


# ---------------------------------------------------------------------------
# siunitx
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("latex", "expected"),
    [
        ("\\SI{3.0e8}{\\metre\\per\\second}", "3.0 × 10⁸ m·s⁻¹"),
        ("\\qty{9.81}{\\metre\\per\\second\\squared}", "9.81 m·s⁻²"),
        ("\\si{\\kilo\\gram}", "kg"),
        ("\\si{\\joule\\per\\mole\\per\\kelvin}", "J·mol⁻¹·K⁻¹"),
        ("\\SI{25}{\\celsius}", "25 °C"),
        ("\\SI{50}{\\percent}", "50 %"),
        ("\\num{1.5e-3}", "1.5 × 10⁻³"),
        ("\\num{12345.678}", "12345.678"),
        ("\\ang{45}", "45°"),
        ("\\SIrange{10}{20}{\\metre}", "10–20 m"),
        ("\\SI{1.5+-0.2}{\\milli\\ampere}", "1.5 ± 0.2 mA"),
        ("\\si{m.s^{-1}}", "m·s⁻¹"),
        ("\\si{\\square\\metre}", "m²"),
    ],
)
def test_siunitx(latex: str, expected: str) -> None:
    out, warnings = convert(latex)
    assert out.strip() == expected
    assert not any("Unknown macro" in w for w in warnings)


def test_si_helpers_directly() -> None:
    assert format_si_number("6.022e23") == "6.022 × 10²³"
    assert format_si_unit("") == ""
    assert format_si_quantity("90", "\\degree") == "90°"


# ---------------------------------------------------------------------------
# Math labels and equation references
# ---------------------------------------------------------------------------


def test_math_labels_stripped_and_equations_tagged() -> None:
    out, _ = convert(
        "\\begin{equation}\\label{eq:e} E = mc^2 \\end{equation}"
        "\\begin{align}a &= b \\label{eq:a}\\\\ c &= d \\nonumber \\\\ e &= f\\end{align}"
        "\\begin{align*}x&=y\\\\z&=w\\end{align*}"
        "\\begin{equation*}q\\label{eq:none}\\end{equation*}"
        "Eqs.~\\eqref{eq:e}, \\eqref{eq:a}, \\ref{eq:a}, \\cref{eq:e}."
    )
    assert "\\label" not in out and "\\nonumber" not in out
    assert "$$E = mc^2 \\tag{1}$$" in out
    assert "a &= b \\tag{2}" in out and "e &= f \\tag{3}" in out
    assert "c &= d \\tag" not in out
    assert "\\begin{aligned}" in out  # align* keeps alignment inside $$
    assert "Eqs. (1), (2), 2, Equation (1)." in flat(out)


def test_unresolved_reference_kept_with_warning() -> None:
    out, warnings = convert("See \\ref{nope} and \\pageref{sec}.")
    assert "[ref:nope]" in out and "[ref:sec]" in out
    assert any("Unresolved references" in w and "nope" in w for w in warnings)


def test_section_numbering_and_nameref() -> None:
    out, _ = convert(
        "\\section{Intro}\\label{s:i}\\subsection{Deep}\\label{s:d}"
        "\\section*{Unnumbered}\\section{Next}\\label{s:n}"
        "\\ref{s:i}/\\ref{s:d}/\\ref{s:n}/\\nameref{s:d}/\\Cref{s:n}"
    )
    assert "1/1.1/2/Deep/Section 2" in out


def test_chapter_numbering() -> None:
    out, _ = convert("\\chapter{A}\\section{B}\\label{b}\\ref{b}")
    assert "1.1" in out


# ---------------------------------------------------------------------------
# Beamer
# ---------------------------------------------------------------------------


def test_beamer_frames_and_overlays() -> None:
    out, warnings = convert(
        "\\documentclass{beamer}\\begin{document}"
        "\\begin{frame}[fragile]{First}{Subtitle}"
        "\\begin{itemize}[<+->]\\item<1-> A \\pause\\item<2-> B\\end{itemize}"
        "\\only<2>{Two} \\visible<3>{Three} \\uncover<4>{Four} \\invisible<5>{Gone} "
        "\\alert<2>{Hot}"
        "\\begin{block}{Key}Body\\end{block}"
        "\\note{Speaker note}"
        "\\end{frame}"
        "\\section{Part}"
        "\\begin{frame}\\frametitle{Second}Text\\end{frame}"
        "\\end{document}"
    )
    assert "## First" in out and "*Subtitle*" in out
    assert "- A" in out and "- B" in out
    assert "Two" in out and "Three" in out and "Four" in out
    assert "Gone" not in out
    assert "**Hot**" in out
    assert "> **Key**" in out and "> Body" in out
    assert "> **Note:** Speaker note" in out
    assert "### Second" in out  # frames nest under sections once one appears
    for leaked in ("<1->", "<+->", "[fragile]", "\\pause"):
        assert leaked not in out
    assert not any("frame" in w for w in warnings)


class TestIncludeEdgeCases:
    def test_import_without_directory_left_alone(self, tmp_path: Path) -> None:
        from leafpress.importer.tex_includes import expand_includes

        warnings: list[str] = []
        assert expand_includes("\\import{x}", tmp_path, warnings) == "\\import{x}"
        assert warnings == []

    def test_depth_limit(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from leafpress.importer import tex_includes

        monkeypatch.setattr(tex_includes, "MAX_INCLUDE_DEPTH", 3)
        for i in range(6):
            (tmp_path / f"f{i}.tex").write_text(f"L{i} \\input{{f{i + 1}}}")
        warnings: list[str] = []
        out = tex_includes.expand_includes("\\input{f0}", tmp_path, warnings)
        assert "L2" in out and "L3" not in out
        assert any("nested too deeply" in w for w in warnings)

    def test_unreadable_include_reported(self, tmp_path: Path) -> None:
        from leafpress.importer.tex_includes import expand_includes

        (tmp_path / "bin.tex").write_bytes(b"\xff\xfe\x00bad")
        warnings: list[str] = []
        assert expand_includes("\\input{bin}", tmp_path, warnings) == ""
        assert any("Could not read included file bin" in w for w in warnings)

    def test_explicit_extension_kept(self, tmp_path: Path) -> None:
        from leafpress.importer.tex_includes import expand_includes

        (tmp_path / "part.v2.tex").write_text("versioned")
        assert expand_includes("\\input{part.v2}", tmp_path, []) == "versioned"


class TestSiunitxEdgeCases:
    def test_literal_and_macro_units_mixed(self) -> None:
        assert format_si_unit("\\kilo\\gram\\per m") == "kg·m⁻¹"

    def test_tothe_power(self) -> None:
        assert format_si_unit("\\metre\\tothe{4}") == "m⁴"

    def test_quantity_without_unit_and_range_without_unit(self) -> None:
        from leafpress.importer.tex_symbols import format_si_range

        assert format_si_quantity("42", "") == "42"
        assert format_si_range("1", "5") == "1–5"
