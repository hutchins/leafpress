# HTML Output

LeafPress can generate a self-contained static HTML file from your MkDocs project — a single `.html` file with all styles embedded inline. No external dependencies, no build tools, just open it in a browser.

## Usage

```bash
# Generate HTML
leafpress convert /path/to/project -f html -o dist/

# Generate all formats at once
leafpress convert /path/to/project -f all -o dist/
```

## What You Get

The HTML output includes:

- **Navigation sidebar** — fixed left panel with links to all pages
- **Cover page** — branded title, logo, version, and date
- **Table of contents** — linked entries for quick navigation
- **All content** — rendered from your Markdown with syntax highlighting, tables, admonitions, and task lists
- **Print styles** — the sidebar hides and content reflows when printing via `Ctrl+P`
- **Footer** — git version info and branding

## Features

| Feature | Supported |
|---|---|
| Branding (logo, colors, company) | Yes |
| Cover page | Yes |
| Table of contents | Yes |
| Syntax highlighting (Pygments) | Yes |
| Tables | Yes |
| Admonitions | Yes |
| Task lists (checkboxes) | Yes |
| Images | Yes |
| Code blocks | Yes |
| Emoji shortcodes | Yes |
| Mermaid diagrams | Yes |
| Annotations | Yes |

## Options

All standard CLI options apply:

```bash
leafpress convert . -f html \
    --config leafpress.yml \
    --no-cover-page \
    --no-toc \
    -o dist/
```

## Styling

The HTML output uses your branding config for:

- **Primary color** — headings, links, sidebar accent
- **Logo** — displayed on cover page
- **Company/project name** — cover page and sidebar header
- **Footer** — git info, custom text

Colors are applied via CSS custom properties (`--lp-primary`), making it easy to further customize if needed.

## When to Use HTML

- **Sharing documentation** without requiring Word or a PDF reader
- **Browser-based review** with clickable navigation
- **Printing** via the browser's built-in print dialog
- **Embedding** in wikis, intranets, or other web-based systems
- **Lightweight alternative** when PDF is overkill
