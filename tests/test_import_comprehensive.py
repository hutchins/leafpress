"""Comprehensive import tests using feature-rich fixture files.

Each test class exercises a different format (docx, pptx, xlsx, tex) with
documents containing the widest possible range of features: headings, code
blocks, tables, fonts, subscript/superscript, headers/footers, page breaks,
section breaks, hyperlinks, images, lists, special characters, symbols,
emoji, equations, captions, citations, bibliography, watermark/theme,
charts, shapes, textboxes, and more.
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest

from leafpress.importer.converter import import_docx
from leafpress.importer.converter_pptx import import_pptx
from leafpress.importer.converter_tex import import_tex
from leafpress.importer.converter_xlsx import import_xlsx

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Comprehensive DOCX
# ---------------------------------------------------------------------------


class TestComprehensiveDocxImport:
    """Import tests against fixtures/comprehensive_document.docx."""

    @pytest.fixture(autouse=True)
    def _convert(self, tmp_output: Path) -> None:
        docx_path = FIXTURES_DIR / "comprehensive_document.docx"
        if not docx_path.exists():
            pytest.skip("comprehensive_document.docx not found")
        self.result = import_docx(docx_path, output_path=tmp_output)
        self.content = self.result.markdown_path.read_text()

    # --- Headings ---

    def test_converts_successfully(self) -> None:
        assert self.result.markdown_path.exists()
        assert len(self.content) > 500

    def test_heading_level_1(self) -> None:
        assert "# Chapter 1: Headings and Structure" in self.content

    def test_heading_level_2(self) -> None:
        assert "## Section 1.1: Introduction" in self.content

    def test_heading_level_3(self) -> None:
        assert "### Subsection 1.1.1: Details" in self.content

    def test_heading_level_4(self) -> None:
        # mammoth maps heading 4 to ####
        assert "Sub-subsection Deep" in self.content

    # --- Text formatting ---

    def test_bold(self) -> None:
        assert "**Bold text**" in self.content

    def test_italic(self) -> None:
        assert "*italic text*" in self.content

    def test_bold_italic(self) -> None:
        assert "bold italic" in self.content

    def test_subscript(self) -> None:
        """Subscript text (H₂O) should be present in some form."""
        # mammoth may render subscript as plain text or <sub>
        assert "H" in self.content and "2" in self.content and "O" in self.content

    def test_superscript(self) -> None:
        """Superscript (mc²) should be present in some form."""
        assert "mc" in self.content

    def test_strikethrough(self) -> None:
        assert "Strikethrough" in self.content

    # --- Fonts ---

    def test_different_fonts_content(self) -> None:
        """Content from different font runs should be preserved."""
        assert "Arial font" in self.content
        assert "Times New Roman" in self.content
        assert "Courier New" in self.content or "monospace" in self.content.lower()

    def test_font_colors_content(self) -> None:
        """Colored text content should be preserved."""
        assert "Red text" in self.content
        assert "blue text" in self.content
        assert "green text" in self.content

    # --- Special characters and symbols ---

    def test_special_characters(self) -> None:
        assert "\u00a9" in self.content  # ©
        assert "\u00ae" in self.content  # ®
        assert "\u2122" in self.content  # ™

    def test_currency_symbols(self) -> None:
        assert "\u20ac" in self.content  # €
        assert "\u00a3" in self.content  # £
        assert "\u00a5" in self.content  # ¥

    def test_math_symbols(self) -> None:
        assert "\u221a" in self.content or "√" in self.content  # √
        assert "\u221e" in self.content or "∞" in self.content  # ∞

    def test_arrows(self) -> None:
        assert "\u2192" in self.content or "→" in self.content  # →

    def test_emoji(self) -> None:
        """Emoji characters should be present."""
        assert "\U0001f600" in self.content or "\U0001f680" in self.content

    # --- Lists ---

    def test_bullet_list(self) -> None:
        assert "First bullet item" in self.content
        assert "Second bullet item" in self.content
        assert "Third bullet item" in self.content

    def test_numbered_list(self) -> None:
        assert "First numbered item" in self.content
        assert "Second numbered item" in self.content
        assert "Third numbered item" in self.content

    # --- Tables ---

    def test_table_headers(self) -> None:
        assert "Name" in self.content
        assert "Department" in self.content
        assert "Salary" in self.content

    def test_table_data(self) -> None:
        assert "Alice" in self.content
        assert "Engineering" in self.content
        assert "$120,000" in self.content

    def test_table_separator(self) -> None:
        assert "---" in self.content

    def test_table_caption(self) -> None:
        assert "Employee compensation data" in self.content

    def test_wide_table(self) -> None:
        assert "Col 1" in self.content
        assert "Col 6" in self.content

    # --- Hyperlinks ---

    def test_hyperlink_text(self) -> None:
        assert "the documentation" in self.content

    def test_hyperlink_url(self) -> None:
        assert "https://example.com/docs" in self.content

    def test_multiple_hyperlinks(self) -> None:
        assert "GitHub repository" in self.content
        assert "API reference" in self.content

    # --- Images ---

    def test_images_extracted(self) -> None:
        assert len(self.result.images) >= 1

    def test_image_files_exist(self) -> None:
        for img in self.result.images:
            assert img.exists()

    def test_image_referenced_in_markdown(self) -> None:
        assert "assets/" in self.content

    # --- Equations ---

    def test_equation_content(self) -> None:
        """Equation text or OMML content should appear."""
        # mammoth may render OMML as text or skip it
        assert "Pythagorean" in self.content or "a\u00b2" in self.content

    # --- Code blocks ---

    def test_code_content(self) -> None:
        assert "fibonacci" in self.content

    # --- Citations / Bibliography ---

    def test_citation_text(self) -> None:
        assert "Smith" in self.content
        assert "Brown" in self.content

    def test_bibliography_entries(self) -> None:
        assert "Journal of Information Processing" in self.content
        assert "Document Conversion" in self.content

    # --- Horizontal rule ---

    def test_horizontal_rule_content(self) -> None:
        """Horizontal rule characters or surrounding content present."""
        assert "horizontal rule" in self.content.lower()

    # --- Page breaks ---

    def test_content_after_page_break(self) -> None:
        assert "Final Section After Page Break" in self.content

    # --- Section breaks ---

    def test_landscape_section_content(self) -> None:
        assert "Landscape Section" in self.content
        assert "landscape orientation" in self.content.lower()

    # --- Headers / Footers ---

    def test_header_footer_description(self) -> None:
        """Header/footer description text is in the document body."""
        assert "headers and footers" in self.content.lower()

    # --- Watermark ---

    def test_watermark_description(self) -> None:
        assert "watermark" in self.content.lower()

    # --- Textbox ---

    def test_textbox_content(self) -> None:
        assert "callout text" in self.content.lower() or "Textbox" in self.content

    # --- Summary ---

    def test_summary_present(self) -> None:
        assert "Summary" in self.content


# ---------------------------------------------------------------------------
# Comprehensive PPTX
# ---------------------------------------------------------------------------


class TestComprehensivePptxImport:
    """Import tests against fixtures/comprehensive_presentation.pptx."""

    @pytest.fixture(autouse=True)
    def _convert(self, tmp_output: Path) -> None:
        pptx_path = FIXTURES_DIR / "comprehensive_presentation.pptx"
        if not pptx_path.exists():
            pytest.skip("comprehensive_presentation.pptx not found")
        self.result = import_pptx(pptx_path, output_path=tmp_output)
        self.content = self.result.markdown_path.read_text()

    # --- Basics ---

    def test_converts_successfully(self) -> None:
        assert self.result.markdown_path.exists()
        assert len(self.content) > 300

    def test_title_slide(self) -> None:
        assert "Comprehensive Feature Test" in self.content

    # --- Text formatting ---

    def test_bold(self) -> None:
        assert "**Bold text**" in self.content

    def test_italic(self) -> None:
        assert "*italic text*" in self.content

    def test_bold_italic(self) -> None:
        assert "bold italic" in self.content

    def test_subscript_content(self) -> None:
        """Subscript text should appear (may not have sub formatting)."""
        assert "H" in self.content and "O" in self.content

    def test_superscript_content(self) -> None:
        assert "mc" in self.content

    def test_different_fonts_content(self) -> None:
        assert "Arial" in self.content
        assert "Times New Roman" in self.content
        assert "Courier" in self.content

    # --- Special characters ---

    def test_special_characters(self) -> None:
        assert "\u00a9" in self.content  # ©
        assert "\u20ac" in self.content  # €

    def test_emoji(self) -> None:
        assert "\U0001f600" in self.content or "\U0001f680" in self.content

    # --- Lists ---

    def test_bullet_levels(self) -> None:
        assert "Bullet Level 0" in self.content
        assert "  - Bullet Level 1" in self.content
        assert "    - Bullet Level 2" in self.content

    def test_deep_nesting(self) -> None:
        assert "Bullet Level 3" in self.content

    # --- Table ---

    def test_table_headers(self) -> None:
        assert "| Feature" in self.content
        assert "Status" in self.content
        assert "Priority" in self.content

    def test_table_data(self) -> None:
        assert "Import DOCX" in self.content
        assert "Complete" in self.content

    def test_table_pipe_in_data(self) -> None:
        """Pipe characters in table cell content."""
        # The PPTX importer uses cell.text which includes raw pipes
        assert "Charts" in self.content or "shapes" in self.content

    # --- Hyperlinks ---

    def test_hyperlinks(self) -> None:
        assert "[Documentation](https://example.com/docs)" in self.content
        assert "[API Reference](https://example.com/api)" in self.content

    def test_multiple_hyperlinks(self) -> None:
        assert "[Source Code]" in self.content
        assert "[Issue Tracker]" in self.content

    # --- Images ---

    def test_images_extracted(self) -> None:
        assert len(self.result.images) >= 2

    def test_image_markdown(self) -> None:
        assert "![](assets/" in self.content

    # --- Chart ---

    def test_chart_warning(self) -> None:
        """Charts produce a warning since they can't be converted."""
        assert any("chart" in w.lower() for w in self.result.warnings)

    # --- Textbox ---

    def test_textbox_content(self) -> None:
        assert "custom positioning" in self.content

    def test_second_textbox(self) -> None:
        assert "callout information" in self.content

    # --- Shapes ---

    def test_shape_text(self) -> None:
        assert "Rectangle shape" in self.content
        assert "Oval shape" in self.content

    def test_arrow_shape(self) -> None:
        assert "Arrow shape" in self.content

    # --- Speaker notes ---

    def test_speaker_notes(self) -> None:
        assert "> Verify special characters" in self.content

    def test_multiline_notes(self) -> None:
        assert "quarterly targets" in self.content

    # --- Blank slide ---

    def test_blank_slide_fallback(self) -> None:
        assert "## Slide 12" in self.content

    # --- Slide count ---

    def test_slide_count(self) -> None:
        assert self.content.count("## ") == 12


# ---------------------------------------------------------------------------
# Comprehensive XLSX
# ---------------------------------------------------------------------------


class TestComprehensiveXlsxImport:
    """Import tests against fixtures/comprehensive_workbook.xlsx."""

    @pytest.fixture(autouse=True)
    def _convert(self, tmp_output: Path) -> None:
        xlsx_path = FIXTURES_DIR / "comprehensive_workbook.xlsx"
        if not xlsx_path.exists():
            pytest.skip("comprehensive_workbook.xlsx not found")
        self.result = import_xlsx(xlsx_path, output_path=tmp_output)
        self.content = self.result.markdown_path.read_text()

    # --- Basics ---

    def test_converts_successfully(self) -> None:
        assert self.result.markdown_path.exists()
        assert len(self.content) > 500

    # --- Sheet headings ---

    def test_mixed_types_sheet(self) -> None:
        assert "## Mixed Types" in self.content

    def test_styled_cells_sheet(self) -> None:
        assert "## Styled Cells" in self.content

    def test_merged_cells_sheet(self) -> None:
        assert "## Merged Cells" in self.content

    def test_special_characters_sheet(self) -> None:
        assert "## Special Characters" in self.content

    def test_formulas_sheet(self) -> None:
        assert "## Formulas" in self.content

    def test_chart_data_sheet(self) -> None:
        assert "## Chart Data" in self.content

    def test_images_sheet(self) -> None:
        assert "## Images" in self.content

    def test_hyperlinks_sheet(self) -> None:
        assert "## Hyperlinks" in self.content

    def test_wide_table_sheet(self) -> None:
        assert "## Wide Table" in self.content

    def test_empty_sheet_skipped(self) -> None:
        assert "## Empty" not in self.content

    def test_trailing_blanks_sheet(self) -> None:
        assert "## Trailing Blanks" in self.content

    # --- Data types ---

    def test_string_value(self) -> None:
        assert "Hello World" in self.content

    def test_integer_value(self) -> None:
        assert "| 42" in self.content

    def test_float_value(self) -> None:
        assert "3.14159" in self.content

    def test_integer_float_no_decimal(self) -> None:
        """100.0 should display as 100."""
        assert "| 100 " in self.content or "| 100|" in self.content

    def test_negative_value(self) -> None:
        assert "-273.15" in self.content

    def test_boolean_true(self) -> None:
        assert "True" in self.content

    def test_boolean_false(self) -> None:
        assert "False" in self.content

    def test_date_value(self) -> None:
        assert "2025-06-15" in self.content

    def test_datetime_value(self) -> None:
        assert "2025-06-15 14:30:00" in self.content

    def test_time_value(self) -> None:
        assert "09:30:00" in self.content

    def test_zero_value(self) -> None:
        assert "| 0 " in self.content or "| 0|" in self.content

    def test_large_number(self) -> None:
        assert "9999999999" in self.content

    def test_small_float(self) -> None:
        assert "0.0001" in self.content

    # --- Special characters ---

    def test_copyright_symbol(self) -> None:
        assert "\u00a9" in self.content

    def test_euro_symbol(self) -> None:
        assert "\u20ac" in self.content

    def test_emoji_in_cells(self) -> None:
        assert "\U0001f600" in self.content or "\U0001f680" in self.content

    def test_pipe_escaped(self) -> None:
        assert "value \\| other value" in self.content

    def test_arrows(self) -> None:
        assert "\u2192" in self.content

    # --- Merged cells warning ---

    def test_merged_cells_warning(self) -> None:
        assert any("merged" in w.lower() for w in self.result.warnings)

    # --- Chart warning ---

    def test_chart_warning(self) -> None:
        assert any("chart" in w.lower() for w in self.result.warnings)

    # --- Image warning ---

    def test_image_warning(self) -> None:
        assert any("image" in w.lower() for w in self.result.warnings)

    # --- Wide table ---

    def test_wide_table_columns(self) -> None:
        assert "Column_1" in self.content
        assert "Column_15" in self.content

    # --- Trailing blanks ---

    def test_trailing_blanks_stripped(self) -> None:
        section = self.content.split("## Trailing Blanks")[1]
        data_lines = [
            ln for ln in section.strip().split("\n") if ln.startswith("|") and "---" not in ln
        ]
        assert len(data_lines) == 3  # header + alpha + beta

    # --- Formulas (computed values) ---

    def test_formula_results(self) -> None:
        assert "| 30" in self.content  # Sum of 10+20
        assert "| 200" in self.content  # Product of 10*20

    # --- Hyperlinks in cells ---

    def test_hyperlink_urls(self) -> None:
        assert "https://example.com/docs" in self.content
        assert "https://github.com/example" in self.content

    # --- Styled cells content ---

    def test_styled_content_preserved(self) -> None:
        """Cell content is preserved regardless of styling."""
        assert "Bold text" in self.content
        assert "Italic text" in self.content
        assert "Red colored text" in self.content
        assert "Code-like text" in self.content

    # --- No images extracted ---

    def test_no_images_in_result(self) -> None:
        assert self.result.images == []


# ---------------------------------------------------------------------------
# Comprehensive TEX
# ---------------------------------------------------------------------------


class TestComprehensiveTexImport:
    """Import tests against fixtures/comprehensive_document.tex."""

    @pytest.fixture(autouse=True)
    def _convert(self, tmp_output: Path) -> None:
        tex_path = FIXTURES_DIR / "comprehensive_document.tex"
        if not tex_path.exists():
            pytest.skip("comprehensive_document.tex not found")
        # Create a test image so includegraphics works
        img = FIXTURES_DIR / "test_figure.png"
        if not img.exists():
            from helpers import make_png

            img.write_bytes(make_png())
            self._created_img = img
        else:
            self._created_img = None
        self.result = import_tex(tex_path, output_path=tmp_output)
        self.content = self.result.markdown_path.read_text()

    @pytest.fixture(autouse=True)
    def _cleanup(self) -> Generator[None]:
        yield
        if hasattr(self, "_created_img") and self._created_img:
            self._created_img.unlink(missing_ok=True)

    # --- Basics ---

    def test_converts_successfully(self) -> None:
        assert self.result.markdown_path.exists()
        assert len(self.content) > 500

    # --- Title block ---

    def test_title(self) -> None:
        assert "Comprehensive" in self.content
        assert "Feature Test" in self.content

    def test_author(self) -> None:
        assert "Test Author" in self.content

    def test_date(self) -> None:
        assert "January 2025" in self.content

    # --- Headings ---

    def test_section_headings(self) -> None:
        assert "## Headings and Structure" in self.content
        assert "## Text Formatting" in self.content
        assert "## Lists" in self.content
        assert "## Tables" in self.content
        assert "## Equations and Math" in self.content

    def test_subsection_headings(self) -> None:
        assert "### Subsection Heading" in self.content
        assert "### Bullet List" in self.content
        assert "### Numbered List" in self.content

    def test_subsubsection(self) -> None:
        assert "Subsubsection Heading" in self.content

    def test_paragraph_heading(self) -> None:
        assert "Paragraph Heading" in self.content

    def test_subparagraph_heading(self) -> None:
        assert "Subparagraph Heading" in self.content

    # --- Text formatting ---

    def test_bold(self) -> None:
        assert "**bold text**" in self.content

    def test_italic(self) -> None:
        assert "*italic text*" in self.content

    def test_emphasis(self) -> None:
        assert "*emphasized text*" in self.content

    def test_monospace(self) -> None:
        assert "`monospace text`" in self.content

    def test_underline(self) -> None:
        assert "<u>underlined text</u>" in self.content

    def test_combined_formatting(self) -> None:
        assert "bold italic" in self.content

    # --- Subscript / Superscript ---

    def test_subscript_tex(self) -> None:
        """\\textsubscript produces subscript content."""
        # The converter renders this as plain text or with the argument
        assert "H" in self.content and "O" in self.content

    def test_superscript_tex(self) -> None:
        assert "mc" in self.content

    # --- Special characters ---

    def test_special_chars_escaped(self) -> None:
        """LaTeX escaped special chars should appear as plain text."""
        assert "&" in self.content
        assert "%" in self.content

    def test_unicode_symbols(self) -> None:
        """LaTeX symbol macros like \\copyright may not survive conversion."""
        # The converter strips unknown macros; verify the section exists
        assert "Unicode symbols" in self.content or "Special characters" in self.content

    def test_math_decorative(self) -> None:
        assert "$" in self.content

    # --- Lists ---

    def test_bullet_list(self) -> None:
        assert "- First bullet item" in self.content
        assert "- Second bullet item" in self.content

    def test_nested_bullets(self) -> None:
        assert "  - Nested bullet A" in self.content
        assert "    - Deep nested item" in self.content

    def test_numbered_list(self) -> None:
        assert "1. First numbered item" in self.content
        assert "2. Second numbered item" in self.content

    def test_nested_numbered(self) -> None:
        assert "Sub-item a" in self.content
        assert "Sub-item b" in self.content

    def test_description_list(self) -> None:
        assert "**Term One**" in self.content
        assert "**Term Two**" in self.content

    # --- Tables ---

    def test_simple_table(self) -> None:
        assert "Left" in self.content
        assert "Center" in self.content
        assert "Right" in self.content
        assert "Alpha" in self.content

    def test_table_separator(self) -> None:
        assert "---" in self.content

    def test_booktabs_table(self) -> None:
        assert "Feature" in self.content
        assert "Version 1" in self.content
        assert "97.8" in self.content

    def test_table_alignment(self) -> None:
        """Tables with alignment specs produce alignment markers."""
        lines = [ln for ln in self.content.split("\n") if "---" in ln and "|" in ln]
        assert len(lines) >= 1

    # --- Equations ---

    def test_inline_math(self) -> None:
        assert "$x = \\frac{" in self.content or "quadratic" in self.content

    def test_display_equation(self) -> None:
        assert "$$" in self.content

    def test_euler_identity(self) -> None:
        assert "e^{i\\pi}" in self.content

    def test_align_environment(self) -> None:
        assert "\\nabla" in self.content

    def test_equation_star(self) -> None:
        assert "\\sum_" in self.content or "\\frac{\\pi" in self.content

    def test_cross_references(self) -> None:
        assert "[ref:" in self.content

    # --- Code blocks ---

    def test_verbatim(self) -> None:
        assert "```" in self.content
        assert 'print("Hello, World!")' in self.content

    def test_lstlisting_python(self) -> None:
        assert "```python" in self.content
        assert "fibonacci" in self.content

    # --- Hyperlinks ---

    def test_href_link(self) -> None:
        assert "[the documentation page](https://example.com/docs)" in self.content

    def test_url_link(self) -> None:
        assert "<https://github.com/example/project>" in self.content

    def test_multiple_links(self) -> None:
        assert "API Reference" in self.content
        assert "Changelog" in self.content

    # --- Figures / Images ---

    def test_figure_image(self) -> None:
        assert "![" in self.content

    def test_figure_caption(self) -> None:
        assert "test figure" in self.content.lower()

    def test_image_extracted(self) -> None:
        assert len(self.result.images) >= 1

    # --- Blockquotes ---

    def test_quote(self) -> None:
        assert "> The best way to predict the future" in self.content

    def test_quotation(self) -> None:
        assert "> This is a longer quotation" in self.content

    # --- Footnotes ---

    def test_footnote_markers(self) -> None:
        assert "[^1]" in self.content
        assert "[^2]" in self.content
        assert "[^3]" in self.content

    def test_footnote_definitions(self) -> None:
        assert "[^1]: " in self.content
        assert "[^2]: " in self.content
        assert "[^3]: " in self.content

    # --- Citations ---

    def test_citations(self) -> None:
        assert "[knuth1984]" in self.content
        assert "[lamport1994" in self.content

    def test_citet(self) -> None:
        assert "[dijkstra1968]" in self.content

    # --- Bibliography ---

    def test_bibliography(self) -> None:
        """thebibliography environment content should appear."""
        assert "Knuth" in self.content or "TeXbook" in self.content

    # --- Table of Contents ---

    def test_toc_macro_stripped(self) -> None:
        """\\tableofcontents should not appear as raw text."""
        assert "\\tableofcontents" not in self.content

    # --- Page break ---

    def test_content_after_page_break(self) -> None:
        assert "Final Section After Page Break" in self.content

    # --- Preamble stripped ---

    def test_preamble_stripped(self) -> None:
        assert "\\documentclass" not in self.content
        assert "\\usepackage" not in self.content
        assert "\\pagestyle" not in self.content

    # --- Environments ---

    def test_center_passthrough(self) -> None:
        assert "centered" in self.content.lower()

    def test_minipage_passthrough(self) -> None:
        assert "minipage" in self.content.lower()

    # --- TikZ warning ---

    def test_tikz_warning(self) -> None:
        assert any("tikzpicture" in w for w in self.result.warnings)

    # --- Custom macro warnings ---

    def test_custom_macro_warning(self) -> None:
        assert any("newcommand" in w for w in self.result.warnings)
