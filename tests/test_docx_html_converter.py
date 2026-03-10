"""Tests for DOCX HTML-to-document converter."""

from pathlib import Path

from docx import Document

from leafpress.docx.html_converter import HtmlToDocxConverter


def _make_converter(tmp_path: Path) -> tuple[Document, HtmlToDocxConverter]:
    doc = Document()
    converter = HtmlToDocxConverter(doc, tmp_path)
    return doc, converter


def test_convert_empty_html(tmp_path: Path) -> None:
    doc, converter = _make_converter(tmp_path)
    converter.convert("")
    converter.convert("   ")
    # No paragraphs added beyond the default
    assert len(doc.paragraphs) == 0


def test_convert_heading(tmp_path: Path) -> None:
    doc, converter = _make_converter(tmp_path)
    converter.convert("<h1>Title</h1>")
    converter.convert("<h2>Subtitle</h2>")
    converter.convert("<h3>Section</h3>")
    assert any(p.text == "Title" for p in doc.paragraphs)
    assert any(p.text == "Subtitle" for p in doc.paragraphs)
    assert any(p.text == "Section" for p in doc.paragraphs)


def test_convert_paragraph(tmp_path: Path) -> None:
    doc, converter = _make_converter(tmp_path)
    converter.convert("<p>Hello world</p>")
    assert any("Hello world" in p.text for p in doc.paragraphs)


def test_convert_bold_italic(tmp_path: Path) -> None:
    doc, converter = _make_converter(tmp_path)
    converter.convert("<p><strong>bold</strong> and <em>italic</em></p>")
    para = doc.paragraphs[0]
    runs = para.runs
    bold_runs = [r for r in runs if r.bold]
    italic_runs = [r for r in runs if r.italic]
    assert len(bold_runs) >= 1
    assert len(italic_runs) >= 1


def test_convert_inline_code(tmp_path: Path) -> None:
    doc, converter = _make_converter(tmp_path)
    converter.convert("<p>Use <code>print()</code> here</p>")
    para = doc.paragraphs[0]
    code_runs = [r for r in para.runs if r.font.name == "Courier New"]
    assert len(code_runs) >= 1


def test_convert_link(tmp_path: Path) -> None:
    doc, converter = _make_converter(tmp_path)
    converter.convert('<p><a href="https://example.com">click</a></p>')
    para = doc.paragraphs[0]
    link_runs = [r for r in para.runs if r.underline]
    assert len(link_runs) >= 1


def test_convert_unordered_list(tmp_path: Path) -> None:
    doc, converter = _make_converter(tmp_path)
    converter.convert("<ul><li>One</li><li>Two</li></ul>")
    texts = [p.text for p in doc.paragraphs]
    assert "One" in texts
    assert "Two" in texts


def test_convert_ordered_list(tmp_path: Path) -> None:
    doc, converter = _make_converter(tmp_path)
    converter.convert("<ol><li>First</li><li>Second</li></ol>")
    texts = [p.text for p in doc.paragraphs]
    assert "First" in texts
    assert "Second" in texts


def test_convert_table(tmp_path: Path) -> None:
    doc, converter = _make_converter(tmp_path)
    converter.convert(
        "<table><tr><th>Header</th></tr><tr><td>Cell</td></tr></table>"
    )
    assert len(doc.tables) == 1
    table = doc.tables[0]
    assert table.cell(0, 0).text == "Header"
    assert table.cell(1, 0).text == "Cell"


def test_convert_code_block(tmp_path: Path) -> None:
    doc, converter = _make_converter(tmp_path)
    converter.convert("<pre><code>x = 1</code></pre>")
    code_paras = [p for p in doc.paragraphs if p.runs and p.runs[0].font.name == "Courier New"]
    assert len(code_paras) >= 1


def test_convert_blockquote(tmp_path: Path) -> None:
    doc, converter = _make_converter(tmp_path)
    converter.convert("<blockquote><p>A quote</p></blockquote>")
    assert any("A quote" in p.text for p in doc.paragraphs)


def test_convert_horizontal_rule(tmp_path: Path) -> None:
    doc, converter = _make_converter(tmp_path)
    converter.convert("<hr>")
    # HR adds a paragraph with a border element
    assert len(doc.paragraphs) >= 1


def test_convert_admonition(tmp_path: Path) -> None:
    doc, converter = _make_converter(tmp_path)
    converter.convert(
        '<div class="admonition note">'
        '<p class="admonition-title">Note</p>'
        "<p>Content here</p>"
        "</div>"
    )
    texts = [p.text for p in doc.paragraphs]
    assert "Note" in texts
    assert any("Content here" in t for t in texts)


def test_convert_definition_list(tmp_path: Path) -> None:
    doc, converter = _make_converter(tmp_path)
    converter.convert("<dl><dt>Term</dt><dd>Definition</dd></dl>")
    texts = [p.text for p in doc.paragraphs]
    assert "Term" in texts
    assert any("Definition" in t for t in texts)


def test_convert_details(tmp_path: Path) -> None:
    doc, converter = _make_converter(tmp_path)
    converter.convert(
        "<details><summary>More info</summary><p>Details here</p></details>"
    )
    texts = [p.text for p in doc.paragraphs]
    assert "More info" in texts


def test_convert_nested_div(tmp_path: Path) -> None:
    doc, converter = _make_converter(tmp_path)
    converter.convert("<div><p>Inside div</p></div>")
    assert any("Inside div" in p.text for p in doc.paragraphs)


def test_convert_image_not_found(tmp_path: Path) -> None:
    doc, converter = _make_converter(tmp_path)
    converter.convert('<img src="nonexistent.png">')
    assert any("Image not found" in p.text for p in doc.paragraphs)


def test_admonition_colors(tmp_path: Path) -> None:
    _, converter = _make_converter(tmp_path)
    # Test various admonition types return different colors
    note_color = converter._admonition_color(["admonition", "note"])
    warning_color = converter._admonition_color(["admonition", "warning"])
    tip_color = converter._admonition_color(["admonition", "tip"])
    default_color = converter._admonition_color(["admonition", "unknown"])
    assert note_color != warning_color
    assert note_color != tip_color
    assert default_color == note_color  # default is same as note
