# Markdown Output

LeafPress can combine all pages from your MkDocs project into a single consolidated Markdown file. This is useful for feeding documentation to LLMs, pasting into wikis, or sharing as a lightweight, portable document.

## Usage

```bash
# Generate consolidated Markdown
leafpress convert /path/to/project -f markdown -o dist/

# Generate all formats at once
leafpress convert /path/to/project -f all -o dist/
```

## What You Get

The Markdown output includes:

- **All pages combined** — every page from your MkDocs nav, concatenated in order with `---` separators
- **Original source preserved** — reads your `.md` files directly, keeping all formatting intact
- **YAML front matter** — title, author, company, date, and git version metadata (when cover page is enabled)
- **Table of contents** — Markdown TOC with anchor links generated from your nav structure
- **Section dividers** — nav sections rendered as headings to preserve document structure

## Features

| Feature | Supported |
|---|---|
| Branding metadata (front matter) | Yes |
| Cover page (YAML front matter) | Yes |
| Table of contents | Yes |
| Page separators | Yes |
| Section headings | Yes |
| Original Markdown preserved | Yes |
| Missing page handling | Skipped gracefully |

## Options

All standard CLI options apply:

```bash
leafpress convert . -f markdown \
    --config leafpress.yml \
    --no-cover-page \
    --no-toc \
    -o dist/
```

## When to Use Markdown

- **LLM context** — feed an entire documentation site to a language model as a single file
- **Wiki paste** — drop into Confluence, Notion, GitHub wiki, or any Markdown-compatible platform
- **Offline sharing** — email or message a single self-contained document
- **Archival** — snapshot all docs in a portable, version-controllable text format
- **Content review** — read through all documentation in one place without navigating between pages
