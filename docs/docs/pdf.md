# PDF Output

leafpress uses [WeasyPrint](https://doc.courtbouillon.org/weasyprint/) to render HTML/CSS to PDF.

## PDF options

Configure PDF output in `leafpress.yml` under the `pdf:` key:

```yaml
pdf:
  page_size: "A4"       # A4 or Letter
  margin_top: "25mm"
  margin_bottom: "25mm"
  margin_left: "20mm"
  margin_right: "20mm"
```

| Field | Default | Description |
|-------|---------|-------------|
| `page_size` | `A4` | Page dimensions (`A4` or `Letter`) |
| `margin_top` | `25mm` | Top page margin |
| `margin_bottom` | `25mm` | Bottom page margin |
| `margin_left` | `20mm` | Left page margin |
| `margin_right` | `20mm` | Right page margin |

Margins accept any CSS length unit: `mm`, `cm`, `in`, `pt`, `px`.

## Cover page

A branded cover page is included by default. Disable it with:

```bash
leafpress convert . --no-cover-page
```

The cover page displays:

- Company logo (if `logo_path` is set)
- `project_name` as the main title
- `subtitle` (if set)
- `company_name`
- `author` and `author_email` (if set)
- `copyright_text` (if set)
- Git version string (if the project is a git repository)

## Table of contents

A table of contents page is included by default. Disable it with:

```bash
leafpress convert . --no-toc
```

## Footer

Each page includes a footer with configurable content. See [Branding & Styling](branding.md#footer) for footer configuration.

## Supported Markdown features

leafpress renders the same Markdown extensions configured in `mkdocs.yml`:

- Standard Markdown (headings, paragraphs, lists, tables, code blocks)
- Syntax-highlighted code (via Pygments)
- Admonitions (`!!! note`, `!!! warning`, etc.)
- Task lists
- Emoji (rendered as inline text or small images)
- Mermaid diagrams (rendered as images via [mermaid.ink](https://mermaid.ink))
- Annotations (rendered as footnote-style references)
- Strikethrough, superscript, subscript
- Definition lists, footnotes

## System dependencies

WeasyPrint requires native libraries. See [Installation](installation.md#weasyprint-system-dependencies) for platform-specific setup.

!!! tip "macOS users"
    Install `cairo pango gdk-pixbuf libffi` via Homebrew — **not** `weasyprint`. On Apple Silicon, you may also need to set `DYLD_LIBRARY_PATH=/opt/homebrew/lib`. Run `leafpress doctor` to check each library individually.

## Troubleshooting

### UnrecognizedImageError

This error occurs when WeasyPrint encounters an image format it cannot decode — most commonly an SVG image when the `librsvg` system library is missing.

**Fix:** Install librsvg for SVG support:

```bash
# macOS
brew install librsvg

# Ubuntu / Debian
sudo apt install librsvg2-dev

# Fedora
sudo dnf install librsvg2-devel
```

Alternatively, convert SVG images to PNG before running LeafPress.

### Other image errors

If you see errors mentioning images during PDF rendering:

1. Check that all images referenced in your docs exist at their expected paths
2. Ensure images are in a supported format (PNG, JPEG, GIF, or SVG with librsvg)
3. Run `leafpress doctor` to verify your system dependencies are correctly installed

### General rendering failures

Run with `--verbose` for full error details:

```bash
leafpress convert . --verbose
```

Use `leafpress doctor` to diagnose missing system libraries:
