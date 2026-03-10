# EPUB Output

LeafPress can generate EPUB files from your MkDocs project — readable on e-readers, tablets, phones, and in apps like Apple Books, Calibre, and Kindle.

## Usage

```bash
# Generate EPUB
leafpress convert /path/to/project -f epub -o dist/

# Generate all formats at once
leafpress convert /path/to/project -f all -o dist/
```

## What You Get

The EPUB output includes:

- **Cover page** — branded title, version, author, and date as the first chapter
- **Table of contents** — EPUB navigation with sections and chapters
- **All content** — rendered from your Markdown with syntax highlighting, tables, admonitions, and task lists
- **Embedded CSS** — styled with your branding colors and readable typography
- **Footer** — git version info and branding in a closing chapter

## Features

| Feature | Supported |
|---|---|
| Branding (colors, company) | Yes |
| Cover page | Yes |
| Table of contents | Yes |
| Syntax highlighting (Pygments) | Yes |
| Tables | Yes |
| Admonitions | Yes |
| Task lists (checkboxes) | Yes |
| Images | Yes |
| Code blocks | Yes |
| Watermark text | Yes |

## Options

All standard CLI options apply:

```bash
leafpress convert . -f epub \
    --config leafpress.yml \
    --no-cover-page \
    --no-toc \
    -o dist/
```

## Styling

The EPUB output uses your branding config for:

- **Primary color** — headings, links, TOC accents
- **Company/project name** — cover page title
- **Author** — EPUB metadata and cover page
- **Footer** — git info, custom text

The CSS is optimized for e-reader displays with serif typography and comfortable line spacing.

## When to Use EPUB

- **Offline reading** on e-readers, tablets, and phones
- **Long-form documentation** that benefits from book-style navigation
- **Distribution** via e-book platforms or internal libraries
- **Archival** in a widely-supported open format
