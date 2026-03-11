# Document Import

LeafPress can import Word (`.docx`), PowerPoint (`.pptx`), and Excel (`.xlsx`) files and convert them to Markdown. This is useful for migrating existing documents into an MkDocs project.

```bash
leafpress import report.docx
leafpress import deck.pptx
leafpress import data.xlsx

# Import multiple files at once — mix and match formats
leafpress import *.docx *.pptx *.xlsx

# Send all output to a directory
leafpress import *.docx *.pptx *.xlsx -o docs/
```

See the [CLI Reference](cli.md#import) for all flags and examples.

---

## Word Import (DOCX)

Word documents are converted using the [mammoth](https://github.com/mwilliamson/python-mammoth) library, which maps Word styles to semantic HTML, then to Markdown.

### What's supported

| Feature | How it's handled |
|---------|-----------------|
| Headings | Mapped to `#`–`######` based on Word heading level |
| Bold / italic | Preserved as `**bold**` and `*italic*` |
| Hyperlinks | Converted to Markdown link syntax |
| Ordered / unordered lists | Converted to Markdown lists |
| Tables | Converted to pipe-style Markdown tables |
| Images | Extracted to an `assets/` directory and referenced via Markdown image syntax |
| Code blocks | Detected by Word style name — use `--code-styles` to specify which styles are code |

### Code block detection

By default, no Word styles are treated as code. Use `--code-styles` to specify which style names should become fenced code blocks:

```bash
leafpress import report.docx --code-styles "Code Block,Source Code"
```

### Limitations

The following Word features are **not currently supported** and may be lost or simplified during import:

| Feature | Reason |
|---------|--------|
| **Track changes / comments** | Mammoth accepts the final document state only — tracked changes and comments are not included in the output. |
| **Headers / footers** | Document headers and footers are not part of the body content and are skipped. |
| **Page breaks / columns** | Page layout is a visual property with no Markdown equivalent. |
| **Text boxes** | Floating text boxes are not part of the main document flow and are skipped by mammoth. |
| **SmartArt / charts** | Rendered as embedded images by Word internally — if `--extract-images` is enabled, they may appear as images, but labels and data are not extractable as text. |
| **Custom fonts / colors** | Mammoth maps semantic styles (bold, italic, headings) but ignores visual-only formatting like font family, size, and color. |
| **Table of contents** | Word TOC fields are not resolved — they appear as static text or are omitted. |
| **Footnotes / endnotes** | Converted to inline text rather than Markdown footnote syntax. |

!!! tip
    For best results, use Word's built-in heading styles (`Heading 1`, `Heading 2`, etc.) rather than manually formatted bold text. Mammoth relies on styles, not visual formatting.

---

## PowerPoint Import (PPTX)

PowerPoint presentations are converted using the [python-pptx](https://python-pptx.readthedocs.io/) library. Each slide becomes a section in the output Markdown.

### What's supported

| Feature | How it's handled |
|---------|-----------------|
| Slide titles | Each slide title becomes an `## H2` heading |
| Untitled slides | Get a fallback heading `## Slide N` |
| Body text | Extracted with paragraph structure preserved |
| Bold / italic | Preserved as `**bold**` and `*italic*` |
| Hyperlinks | Converted to Markdown link syntax |
| Indented text | Rendered as nested bullet lists based on indent level |
| Tables | Converted to pipe-style Markdown tables |
| Images | Extracted to `assets/` and referenced via Markdown image syntax |
| Speaker notes | Included as blockquotes (toggleable) |
| Group shapes | Recursed into — nested shapes are extracted individually |

### Speaker notes

By default, speaker notes are included as Markdown blockquotes beneath each slide:

```markdown
## Quarterly Review

Revenue increased by 15% over the prior quarter.

> Remember to highlight the APAC growth numbers.
```

To omit speaker notes:

```bash
leafpress import deck.pptx --no-notes
```

### Limitations

The following PowerPoint features are **not currently supported** and will be silently skipped during import:

| Feature | Reason |
|---------|--------|
| **SmartArt** | SmartArt diagrams are stored as complex XML structures that python-pptx cannot access. They appear as opaque shapes with no extractable text. |
| **Charts** | Embedded charts (bar, pie, line, etc.) are rendered as OLE objects. The chart data and labels are not accessible through the shape API. |
| **Animations / transitions** | Markdown has no equivalent — these are presentation-only features. |
| **Audio / video** | Embedded media cannot be meaningfully represented in Markdown. |
| **Slide master / layout formatting** | Only content is extracted, not visual styling from the theme. |

!!! tip
    If a slide contains SmartArt or charts, consider replacing them with static images in PowerPoint before importing — images are fully supported and will be extracted to `assets/`.

---

## Excel Import (XLSX)

Excel spreadsheets are converted using the [openpyxl](https://openpyxl.readthedocs.io/) library. Each worksheet becomes a section with a Markdown table.

### What's supported

| Feature | How it's handled |
|---------|-----------------|
| Multiple sheets | Each sheet becomes a `## Sheet Name` section |
| Header row | First row treated as the table header |
| Text values | Rendered as-is |
| Numbers | Integers and floats rendered as strings (whole-number floats drop the `.0`) |
| Dates / times | Formatted as `YYYY-MM-DD` or `HH:MM:SS` |
| Empty cells | Rendered as blank table cells |
| Pipe characters | Escaped to `\|` so they don't break table syntax |
| Empty sheets | Skipped silently |

### Example output

A sheet named "Servers" with three columns produces:

```markdown
## Servers

| Host     | Role     | CPU |
| -------- | -------- | --- |
| web-01   | frontend | 4   |
| db-01    | database | 8   |
```

### Limitations

| Feature | Reason |
|---------|--------|
| **Merged cells** | Merged regions are not unmerged — only the top-left cell value is read. |
| **Formulas** | Cell values are read in data-only mode — you see computed results, not formula text. Cells that have never been calculated in Excel may appear blank. |
| **Charts / images** | Embedded charts and images are not extracted. |
| **Conditional formatting / colors** | Visual-only formatting has no Markdown equivalent. |
| **Multiple header rows** | Only the first row is treated as the header. |

!!! tip
    For best results, save your Excel file in Excel before importing — this ensures all formula results are cached. LeafPress reads cached values, not formulas.

---

## Common options

### Image extraction

The Word and PowerPoint importers extract embedded images to an `assets/` directory next to the output file. To skip image extraction:

```bash
leafpress import report.docx --no-extract-images
leafpress import deck.pptx --no-extract-images
```

### Output path

By default, the output file uses the same stem as the input (e.g., `deck.pptx` → `deck.md`). You can specify a path or directory:

```bash
# Explicit file path (single file only)
leafpress import deck.pptx -o docs/presentation.md

# Directory (creates deck.md inside it)
leafpress import deck.pptx -o docs/
```

When importing multiple files, `--output` must be a directory (or omitted):

```bash
leafpress import *.docx *.pptx *.xlsx -o docs/
```

### Batch import

You can pass multiple files in a single command. Formats can be mixed freely — each file is detected and routed to the appropriate converter:

```bash
# Import everything in one shot
leafpress import report.docx proposal.docx slides.pptx data.xlsx

# Use shell globs to grab all supported files
leafpress import *.docx *.pptx *.xlsx

# Combine with other options
leafpress import *.docx --code-styles "Code Block" --no-extract-images
leafpress import *.pptx --no-notes -o imported/
```

If one file fails (e.g., missing or corrupt), the remaining files are still processed. A summary of failures is shown at the end.
