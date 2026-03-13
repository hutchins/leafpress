# Word Output (DOCX)

leafpress uses [python-docx](https://python-docx.readthedocs.io/) to generate `.docx` files directly from rendered HTML.

## DOCX options

Configure DOCX output in `leafpress.yml` under the `docx:` key:

```yaml
docx:
  template_path: null   # optional path to a .docx template
```

| Field | Default | Description |
|-------|---------|-------------|
| `template_path` | `null` | Path to a `.docx` file used as a style template |

## Custom template

You can provide a `.docx` template to inherit paragraph styles, fonts, and page setup from an existing Word document:

```yaml
docx:
  template_path: "./my-template.docx"
```

The template path is relative to the `leafpress.yml` file.

## Cover page and TOC

Cover page and table of contents are supported in DOCX output, controlled by the same flags as PDF:

```bash
leafpress convert . -f docx --no-cover-page --no-toc
```

## Supported HTML elements

leafpress converts the following Markdown/HTML elements to DOCX:

| Element | DOCX equivalent |
|---------|----------------|
| `h1`–`h6` | Heading 1–6 styles |
| `p` | Normal paragraph |
| `strong`, `b` | Bold run |
| `em`, `i` | Italic run |
| `code` (inline) | Monospace run |
| `pre code` | Code Block style |
| `ul` / `ol` | List Bullet / List Number styles |
| `li` | List item |
| `table` | Word table |
| `th` / `td` | Table cell |
| `a` | Hyperlink |
| `img` | Inline image (local files) |
| `br` | Line break |
| `hr` | Paragraph separator |
| `del`, `s` | Strikethrough run |
| `sub` | Subscript run |
| `sup` | Superscript run |
| `kbd` | Monospace run |
| Emoji images | Unicode emoji character (from `alt` attribute) |
| Admonition blocks | Styled paragraph with title |
| Mermaid diagrams | Inline image (rendered via [mermaid.ink](https://mermaid.ink)) |
| Annotations | Superscript references with footnote block |

## Limitations

- **SVG images are not supported** — `python-docx` only handles raster formats (PNG, JPEG). SVG logos are skipped with a warning; use PNG or JPEG for full compatibility
- Remote images (except those already fetched by the renderer) are skipped in DOCX output
- Complex CSS styling (custom colors, gradients) is not preserved in DOCX

## Google Workspace compatibility

LeafPress DOCX files open correctly in Google Docs. If you use the `watermark` branding option, note that Google Docs renders watermarks as best-effort — positioning and opacity may differ slightly from Word.
