"""Custom markdownify converter for leafpress import."""

from __future__ import annotations

from typing import Any

from markdownify import MarkdownConverter

# markdownify stubs are incomplete — Options and convert_p exist at runtime
_ConverterOptions: Any = getattr(MarkdownConverter, "Options", object)
_convert_p: Any = getattr(MarkdownConverter, "convert_p", None)


class LeafpressMarkdownConverter(MarkdownConverter):
    """Extended MarkdownConverter with leafpress-specific tag handling.

    Customizations:
    - Fenced code blocks (triple-backtick instead of indentation)
    - Pipe tables for <table> elements
    - ATX-style headings
    """

    class Options(_ConverterOptions):
        heading_style = "atx"
        bullets = "-"
        strong_em_symbol = "*"
        wrap = False
        wrap_width = 0

    def convert_pre(self, el: Any, text: str, parent_tags: Any) -> str:
        """Convert <pre> blocks to fenced code blocks."""
        code = text.strip()
        code_el = el.find("code")
        lang = ""
        if code_el and code_el.get("class"):
            for cls in code_el["class"]:
                if cls.startswith("language-"):
                    lang = cls.removeprefix("language-")
                    break
        return f"\n\n```{lang}\n{code}\n```\n\n"

    def convert_table(self, el: Any, text: str, parent_tags: Any) -> str:
        """Convert <table> to pipe-style Markdown table."""
        rows = el.find_all("tr")
        if not rows:
            return text

        table_data: list[list[str]] = []
        for row in rows:
            cells = row.find_all(["td", "th"])
            table_data.append([self._cell_text(cell) for cell in cells])

        if not table_data:
            return text

        col_count = max(len(row) for row in table_data)
        for row in table_data:
            while len(row) < col_count:
                row.append("")

        col_widths = [max(len(row[i]) for row in table_data) for i in range(col_count)]
        col_widths = [max(w, 3) for w in col_widths]

        lines = []
        for idx, row in enumerate(table_data):
            cells = [cell.ljust(col_widths[i]) for i, cell in enumerate(row)]
            lines.append("| " + " | ".join(cells) + " |")
            if idx == 0:
                sep = ["-" * w for w in col_widths]
                lines.append("| " + " | ".join(sep) + " |")

        return "\n\n" + "\n".join(lines) + "\n\n"

    def _cell_text(self, cell: Any) -> str:
        """Extract clean text from a table cell."""
        text = self.convert(str(cell))
        return text.strip().replace("\n", " ")

    convert_thead = _convert_p
    convert_tbody = _convert_p
    convert_tfoot = _convert_p
    convert_tr = _convert_p
    convert_td = _convert_p
    convert_th = _convert_p
