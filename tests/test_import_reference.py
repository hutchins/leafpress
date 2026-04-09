"""Import tests using reference fixture files.

Tests each importable format (pptx, xlsx, tex) against realistic,
pre-built reference documents in tests/fixtures/.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from leafpress.importer.converter_pptx import import_pptx
from leafpress.importer.converter_tex import import_tex
from leafpress.importer.converter_xlsx import import_xlsx

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Reference PPTX: realistic multi-slide presentation
# ---------------------------------------------------------------------------


class TestReferencePptx:
    """Import tests against fixtures/reference_presentation.pptx."""

    @pytest.fixture(autouse=True)
    def _convert(self, tmp_output: Path) -> None:
        pptx_path = FIXTURES_DIR / "reference_presentation.pptx"
        if not pptx_path.exists():
            pytest.skip("reference_presentation.pptx not found")
        self.result = import_pptx(pptx_path, output_path=tmp_output)
        self.content = self.result.markdown_path.read_text()

    def test_converts_successfully(self) -> None:
        assert self.result.markdown_path.exists()
        assert len(self.content) > 200

    def test_slide_titles(self) -> None:
        assert "Q4 2024 Engineering Review" in self.content
        assert "Executive Summary" in self.content
        assert "Achievements" in self.content
        assert "Performance Metrics" in self.content
        assert "Architecture Overview" in self.content
        assert "Resources" in self.content

    def test_untitled_slide_fallback(self) -> None:
        assert "## Slide 7" in self.content

    def test_bold_formatting(self) -> None:
        assert "**99.95% uptime**" in self.content

    def test_italic_formatting(self) -> None:
        assert "*99.9% SLA target*" in self.content

    def test_body_text(self) -> None:
        assert "zero downtime" in self.content

    def test_speaker_notes(self) -> None:
        assert "> Highlight that this is the first quarter" in self.content

    def test_indented_bullets(self) -> None:
        assert "Infrastructure" in self.content
        assert "  - Migrated to Kubernetes 1.28" in self.content
        assert "  - Reduced cloud spend by 18%" in self.content

    def test_deeper_indent(self) -> None:
        assert "    - Supports gradual rollouts" in self.content

    def test_table(self) -> None:
        assert "| Service" in self.content
        assert "API Gateway" in self.content
        assert "0.02%" in self.content
        assert "---" in self.content

    def test_image_extracted(self) -> None:
        assert len(self.result.images) >= 1
        assert self.result.images[0].exists()
        assert "![](assets/" in self.content

    def test_hyperlinks(self) -> None:
        assert "[Project Dashboard](https://dashboard.example.com)" in self.content
        assert "[Runbook Repository](https://github.com/example/runbooks)" in self.content

    def test_slide_count(self) -> None:
        assert self.content.count("## ") == 7


# ---------------------------------------------------------------------------
# Reference XLSX: realistic multi-sheet workbook
# ---------------------------------------------------------------------------


class TestReferenceXlsx:
    """Import tests against fixtures/reference_workbook.xlsx."""

    @pytest.fixture(autouse=True)
    def _convert(self, tmp_output: Path) -> None:
        xlsx_path = FIXTURES_DIR / "reference_workbook.xlsx"
        if not xlsx_path.exists():
            pytest.skip("reference_workbook.xlsx not found")
        self.result = import_xlsx(xlsx_path, output_path=tmp_output)
        self.content = self.result.markdown_path.read_text()

    def test_converts_successfully(self) -> None:
        assert self.result.markdown_path.exists()
        assert len(self.content) > 200

    def test_sheet_headings(self) -> None:
        assert "## Revenue" in self.content
        assert "## Headcount" in self.content
        assert "## Incidents" in self.content
        assert "## Config" in self.content

    def test_empty_sheet_skipped(self) -> None:
        assert "## Empty" not in self.content

    def test_revenue_data(self) -> None:
        assert "North America" in self.content
        assert "2100000" in self.content
        assert "15.2" in self.content

    def test_date_formatting(self) -> None:
        assert "2024-03-31" in self.content
        assert "2024-06-30" in self.content

    def test_integer_floats(self) -> None:
        """Whole-number floats like 120.0 render without decimals."""
        assert "| 120" in self.content
        assert "| 150" in self.content

    def test_none_cells(self) -> None:
        """None cells produce valid table rows."""
        lines = [ln for ln in self.content.split("\n") if ln.startswith("|")]
        for line in lines:
            assert line.endswith("|")

    def test_pipe_chars_escaped(self) -> None:
        assert "Database failover \\| primary down" in self.content
        assert "dark_mode \\| beta_api" in self.content

    def test_timestamp_formatting(self) -> None:
        assert "2024-10-15" in self.content

    def test_no_images(self) -> None:
        assert self.result.images == []


# ---------------------------------------------------------------------------
# Reference TEX: academic_paper.tex (already exists in fixtures)
# ---------------------------------------------------------------------------


class TestReferenceTexAcademic:
    """Import tests against fixtures/academic_paper.tex."""

    @pytest.fixture(autouse=True)
    def _convert(self, tmp_output: Path) -> None:
        tex_path = FIXTURES_DIR / "academic_paper.tex"
        if not tex_path.exists():
            pytest.skip("academic_paper.tex not found")
        self.result = import_tex(tex_path, output_path=tmp_output)
        self.content = self.result.markdown_path.read_text()

    def test_converts_successfully(self) -> None:
        assert self.result.markdown_path.exists()
        assert len(self.content) > 500

    def test_title_and_metadata(self) -> None:
        assert "Convergence Properties" in self.content
        assert "Alice Researcher" in self.content

    def test_section_hierarchy(self) -> None:
        assert "## Introduction" in self.content
        assert "## Theoretical Framework" in self.content
        assert "### Assumptions" in self.content
        assert "## Experiments" in self.content
        assert "## Conclusion" in self.content

    def test_math_preserved(self) -> None:
        assert "$" in self.content
        assert "$$" in self.content

    def test_code_blocks(self) -> None:
        assert "```" in self.content
        assert "loss.backward()" in self.content

    def test_tables(self) -> None:
        assert "Method" in self.content
        assert "MNIST" in self.content
        assert "---" in self.content

    def test_citations(self) -> None:
        assert "[bottou2018]" in self.content

    def test_formatting(self) -> None:
        assert "**Smoothness**" in self.content

    def test_preamble_stripped(self) -> None:
        assert "\\documentclass" not in self.content
        assert "\\usepackage" not in self.content
