---
template: home.html
hide:
  - navigation
  - toc
---

[![PyPI](https://img.shields.io/pypi/v/leafpress?color=blue)](https://pypi.org/project/leafpress/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://github.com/hutchins/leafpress/blob/main/LICENSE)
[![CI](https://github.com/hutchins/leafpress/actions/workflows/ci.yml/badge.svg)](https://github.com/hutchins/leafpress/actions/workflows/ci.yml)

# LeafPress

Convert MkDocs sites to PDF and Word documents with branding.

## Features

- Generate **PDF** and **DOCX** from any MkDocs project
- Branded cover page, table of contents, and footer
- Logo, colors, and metadata via `leafpress.yml`
- Git version info (tag, branch, commit, date) embedded in output
- Convert from **local paths** or **remote git URLs**
- **Desktop UI** — macOS/Linux/Windows menu bar app
- **CI-friendly** — configure entirely via `LEAFPRESS_*` environment variables and `.env` files

## Quick Start

```termynal
$ pip install leafpress
---> 100%
Successfully installed leafpress

$ leafpress init
Created leafpress.yml

$ leafpress convert . -f pdf -o dist/
Converting MkDocs site to PDF...
✓ dist/docs.pdf

$ leafpress convert . -f both -c leafpress.yml -o dist/
Converting MkDocs site to PDF and DOCX...
✓ dist/docs.pdf
✓ dist/docs.docx
```

## Next Steps

- [Installation](installation.md) — system requirements and setup
- [Configuration](configuration.md) — full `leafpress.yml` reference
- [CLI Reference](cli.md) — all commands and flags
- [Desktop UI](ui.md) — menu bar app
- [CI / GitHub Actions](ci.md) — use in pipelines
