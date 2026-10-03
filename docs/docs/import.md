# Document Import

LeafPress can import Word (`.docx`), PowerPoint (`.pptx`), Excel (`.xlsx`), and LaTeX (`.tex`) files and convert them to Markdown. This is useful for migrating existing documents into an MkDocs project.

```bash
leafpress import report.docx
leafpress import deck.pptx
leafpress import data.xlsx
leafpress import paper.tex

# Import multiple files at once — mix and match formats
leafpress import *.docx *.pptx *.xlsx *.tex

# Send all output to a directory
leafpress import *.docx *.pptx *.xlsx *.tex -o docs/
```

See the [CLI Reference](cli.md#import) for all flags and examples.

Files can also be imported from an `http://` or `https://` URL. Downloads are capped at 200 MB. Without `-o`, a URL import is written to the current directory.

### Importing several files

- **A failed file doesn't stop the batch.** Each error names the file it came from, and leafpress continues with the rest.
- **Summary table.** After a multi-file import, a table lists every source with its status, output path (or error), and image and warning counts.
- **Exit code.** The command exits with code 1 if any file failed.
- **Name collisions are refused.** Two inputs that would produce the same output file (e.g. `a/report.docx` and `b/report.docx` with `-o docs/`) would otherwise overwrite each other. The second one is refused with an error; import them separately or give them different `-o` paths.

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

## LaTeX Import (TEX)

LaTeX documents are converted using a native parser ([pylatexenc](https://github.com/phfaist/pylatexenc)). The converter handles the most common academic paper and documentation constructs.

### What's supported

| Feature | How it's handled |
|---------|-----------------|
| Multi-file projects | `\input`, `\include`, `\subfile`, `\import`, `\subimport` are inlined. Paths resolve like LaTeX's (relative to the main file; `\subimport` relative to the including file) and must stay inside the main file's directory. Commented-out includes are ignored, and cycles and missing files produce warnings |
| Headings | `\chapter` → `#`, `\section` → `##`, … `\paragraph` → `#####`, `\subparagraph` → `######` |
| Bold / italic / code | `\textbf` → `**bold**`, `\textit` / `\emph` → `*italic*`, `\texttt` → `` `code` `` (dashes and quotes inside stay literal) |
| Accents and symbols | `\"o` → ö, `\'e` → é, `\c{c}` → ç, `\v{s}` → š, `\ss` → ß, `\&` / `\%` → & / %, `\ldots` → …, and similar |
| Typography | `---` → —, `--` → –, ` ``quotes'' ` → “quotes”, `~` → space |
| Lists | `itemize` → bullets, `enumerate` → numbered, with nesting support |
| Math | Inline `$...$` and display math become `$$...$$` for MathJax/KaTeX. Numbered `equation`/`align`/`gather` rows get `\tag{n}`, starred forms use `aligned`/`gathered`, and `\label`, `\nonumber`, `\notag` are removed |
| Cross-references | `\ref`, `\eqref`, `\autoref`, `\cref`/`\Cref`, and `\nameref` resolve to section, figure, table, theorem, and equation numbers (e.g. "Section 2.1", "(3)", "Figure 1a"), including forward references. Undefined labels (and `\pageref`) stay as `[ref:key]`, with one warning listing them |
| Images | `\includegraphics` resolved relative to `.tex` file, copied to `assets/`. Paths outside the `.tex` file's directory (absolute, `..`, or via symlinks) are skipped with a warning |
| Figures | `\caption` becomes the image alt text plus a numbered `*Figure n: caption*` line |
| Sub-figures | `subfigure` (subcaption) and `\subfloat` (subfig) render each panel with an `(a)`, `(b)`, … caption |
| Tables | `tabular`/`tabular*`/`tabularx` → pipe tables with column alignment. Cell contents are converted (formatting, math, `\&`), and `table` captions become `*Table n: caption*` |
| `\multicolumn` | Content is kept in the first spanned column and the rest are left empty, since Markdown tables can't span columns. A warning is shown once |
| Theorems and proofs | `theorem`, `lemma`, `definition`, … (plus any `\newtheorem`, including shared counters and `\newtheorem*`) → numbered blockquotes like **Theorem 1 (Note).** `proof` ends with ∎ |
| `siunitx` | `\SI`/`\qty`, `\si`/`\unit`, `\num`, `\ang`, `\SIrange`/`\qtyrange`/`\numrange`: `\SI{3e8}{\metre\per\second}` → 3 × 10⁸ m·s⁻¹ |
| Beamer | Each `frame` becomes a heading (from `{title}` or `\frametitle`) followed by its content. Overlay specs (`<2->`, `[<+->]`) and `\pause` are dropped; `\only`/`\visible`/`\uncover` content is kept and `\invisible` content removed. `block` → titled blockquote, `\alert` → bold, `\note` → "Note:" blockquote |
| Links | `\href{url}{text}` → Markdown links, `\url{url}` → angle-bracket URLs |
| Code blocks | `verbatim`, `lstlisting`, `minted` → fenced code blocks (with language detection) |
| Title / author | `\title` and `\author` rendered at top of document |
| Blockquotes | `abstract`, `quote`, `quotation` → blockquotes |
| Footnotes | `\footnote` → Markdown footnote syntax |

### Limitations

| Feature | Reason |
|---------|--------|
| **Custom macros** | `\newcommand` / `\def` definitions are skipped with a warning. Usages of custom macros appear as raw text. |
| **TikZ / PGF diagrams** | `tikzpicture` and `pgfpicture` environments are skipped with a warning. |
| **Bibliography** | `.bib` files are not parsed. `\cite`, `\citet`, `\citep` commands produce bracketed keys. |
| **`\pageref`** | There are no pages in Markdown, so page references stay as `[ref:key]`. |
| **Column spans** | `\multicolumn` content is kept, but the span itself can't be represented in a pipe table. |
| **Beamer overlays** | Slides are flattened: every overlay step's content (except `\invisible`) appears once. |
| **URL imports** | A `.tex` file imported from a URL can't `\input` sibling files, since only that file is downloaded. |
| **EPS/PDF images** | Only raster image formats (PNG, JPG, SVG, etc.) are copied. EPS and PDF images produce a warning. |

!!! tip
    For best results with math, ensure your Markdown renderer supports MathJax or KaTeX.
    Math expressions are passed through verbatim in LaTeX syntax.

---

## Common options

### Image extraction

The Word, PowerPoint, and LaTeX importers extract embedded images to an `assets/` directory next to the output file. To skip image extraction:

```bash
leafpress import report.docx --no-extract-images
leafpress import deck.pptx --no-extract-images
leafpress import paper.tex --no-extract-images
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

### URL import

You can import documents directly from URLs — the file is downloaded to a temp directory, converted, and the temp file is cleaned up automatically:

```bash
# Import a LaTeX paper from a URL
leafpress import https://example.com/paper.tex

# Import a Word document from a URL
leafpress import https://example.com/report.docx -o docs/

# Mix local files and URLs
leafpress import report.docx https://example.com/slides.pptx -o docs/
```

The file type is inferred from the URL path extension (`.docx`, `.pptx`, `.xlsx`, `.tex`). If the URL has no recognized extension, the `Content-Type` header is used as a fallback. URLs that cannot be mapped to a supported format produce an error.

### Batch import

You can pass multiple files and URLs in a single command. Formats can be mixed freely — each source is detected and routed to the appropriate converter:

```bash
# Import everything in one shot
leafpress import report.docx proposal.docx slides.pptx data.xlsx paper.tex

# Use shell globs to grab all supported files
leafpress import *.docx *.pptx *.xlsx *.tex

# Mix local and remote sources
leafpress import *.docx https://example.com/paper.tex -o docs/

# Combine with other options
leafpress import *.docx --code-styles "Code Block" --no-extract-images
leafpress import *.pptx --no-notes -o imported/
```

If one source fails (e.g., missing file, download error, or corrupt document), the remaining sources are still processed. A summary of failures is shown at the end.
