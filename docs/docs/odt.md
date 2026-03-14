# ODT Output

LeafPress can generate OpenDocument Text (`.odt`) files — the open standard format supported by LibreOffice, Google Docs, and other office suites.

## Usage

```bash
# Generate ODT
leafpress convert /path/to/project -f odt -o dist/

# Generate all formats at once
leafpress convert /path/to/project -f all -o dist/
```

## What You Get

The ODT output includes:

- **Styled headings** — color-matched to your branding
- **Cover page** — logo, company name, project title, version, date
- **Table of contents** — text-based TOC listing all pages
- **Formatted content** — paragraphs, bold, italic, inline code, links
- **Tables** — with header row styling and borders
- **Code blocks** — monospace font with light gray background
- **Lists** — bullet and numbered lists with nesting
- **Blockquotes** — italicized with attribution
- **Footer** — branding and git version info on every page

## Features

| Feature | Supported |
|---|---|
| Branding (logo, colors, company) | Yes |
| Cover page | Yes |
| Table of contents | Yes |
| Headings (H1-H4) | Yes |
| Bold / Italic / Code | Yes |
| Tables | Yes |
| Code blocks | Yes |
| Lists (bullet, numbered) | Yes |
| Blockquotes | Yes |
| Images (local files) | Yes |
| Admonitions | Yes |
| Mermaid diagrams | Yes |
| Annotations | Yes |
| Page footer | Yes |

## Options

All standard CLI options apply:

```bash
leafpress convert . -f odt \
    --config leafpress.yml \
    --no-cover-page \
    --no-toc \
    -o dist/
```

## Limitations

- **SVG images are not supported** — `odfpy` only handles raster formats (PNG, JPEG). SVG logos are skipped with a warning; use PNG or JPEG for full compatibility

## Compatibility

ODT files can be opened with:

- **LibreOffice Writer** (full support)
- **Google Docs** (import via upload)
- **Microsoft Word** (File → Open, or convert on import)
- **Apple Pages** (import support)
- **OnlyOffice** (full support)

## When to Use ODT

- **Open-source workflows** where DOCX is not preferred
- **LibreOffice users** who want native format support
- **Cross-platform sharing** with a vendor-neutral format
- **Government or institutional** contexts that require open standards
