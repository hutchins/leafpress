"""Tests for LeafpressMarkdownConverter."""

from __future__ import annotations

from leafpress.importer.markdown_converter import LeafpressMarkdownConverter


def _convert(html: str) -> str:
    return LeafpressMarkdownConverter().convert(html)


class TestOptions:
    def test_headings_use_atx_style(self) -> None:
        result = _convert("<h1>Title</h1><h2>Subtitle</h2>")
        assert "# Title" in result
        assert "## Subtitle" in result

    def test_bullets_use_dash(self) -> None:
        result = _convert("<ul><li>one</li><li>two</li></ul>")
        assert "- one" in result
        assert "- two" in result

    def test_strong_uses_asterisks(self) -> None:
        result = _convert("<p><strong>bold</strong></p>")
        assert "**bold**" in result


class TestConvertPre:
    def test_pre_without_language_is_fenced(self) -> None:
        result = _convert("<pre>print('hi')</pre>")
        assert "```\nprint('hi')\n```" in result

    def test_pre_with_code_language_class(self) -> None:
        result = _convert("<pre><code class=\"language-python\">print('hi')</code></pre>")
        assert "```python" in result
        assert "print('hi')" in result
        assert result.rstrip().endswith("```")

    def test_pre_with_non_language_class_has_no_lang(self) -> None:
        result = _convert('<pre><code class="foo bar">x = 1</code></pre>')
        assert "```\n" in result
        assert "x = 1" in result

    def test_pre_picks_first_language_class(self) -> None:
        result = _convert(
            '<pre><code class="highlighted language-rust extra">fn main() {}</code></pre>'
        )
        assert "```rust" in result


class TestConvertTable:
    def test_simple_table_with_header(self) -> None:
        html = """
            <table>
              <tr><th>Name</th><th>Age</th></tr>
              <tr><td>Alice</td><td>30</td></tr>
              <tr><td>Bob</td><td>25</td></tr>
            </table>
        """
        result = _convert(html)
        assert "| Name" in result
        assert "| Age" in result
        assert "| Alice" in result
        assert "| Bob" in result
        # separator row of dashes
        assert "| ---" in result

    def test_ragged_rows_are_padded(self) -> None:
        html = """
            <table>
              <tr><th>A</th><th>B</th><th>C</th></tr>
              <tr><td>1</td><td>2</td></tr>
            </table>
        """
        result = _convert(html)
        lines = [ln for ln in result.splitlines() if ln.startswith("|")]
        # All table lines should have the same pipe count (4: leading + 3 separators)
        pipe_counts = {ln.count("|") for ln in lines}
        assert pipe_counts == {4}

    def test_columns_padded_to_min_width_three(self) -> None:
        html = "<table><tr><th>A</th></tr><tr><td>B</td></tr></table>"
        result = _convert(html)
        # Header cell "A" padded to width 3 -> "| A   |"
        assert "| A   |" in result
        assert "| --- |" in result

    def test_empty_table_returns_input_text(self) -> None:
        html = "<table></table>"
        result = _convert(html)
        # No pipe-table output when there are no rows
        assert "|" not in result

    def test_cell_with_newlines_is_flattened(self) -> None:
        html = "<table><tr><th>H</th></tr><tr><td>line one<br>line two</td></tr></table>"
        result = _convert(html)
        table_lines = [ln for ln in result.splitlines() if ln.startswith("|")]
        assert any("line one line two" in ln for ln in table_lines)
