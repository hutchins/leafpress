# LeafPress

[![Docs](https://img.shields.io/badge/docs-leafpress.dev-2e7d32)](https://leafpress.dev/)
[![PyPI](https://img.shields.io/pypi/v/leafpress?color=2e7d32)](https://pypi.org/project/leafpress/)
[![License: MIT](https://img.shields.io/badge/License-MIT-2e7d32.svg)](https://github.com/hutchins/leafpress/blob/main/LICENSE)
[![CI](https://github.com/hutchins/leafpress/actions/workflows/ci.yml/badge.svg)](https://github.com/hutchins/leafpress/actions/workflows/ci.yml)

Convert MkDocs (and [Zensical](https://leafpress.dev/zensical/)) sites to PDF, Word, HTML, ODT, EPUB, and Markdown documents with branding.

**[Documentation](https://leafpress.dev/)** · **[GitHub](https://github.com/hutchins/leafpress)** · **[PyPI](https://pypi.org/project/leafpress/)**

## Features

- Generate **PDF**, **DOCX**, **HTML**, **ODT**, **EPUB**, and **Markdown** output from any MkDocs project. HTML is a single self-contained file, and EPUB packages its images
- **Zensical support** (experimental): projects configured with `zensical.toml` convert the same way
- **Document import** — convert Word (`.docx`), PowerPoint (`.pptx`), Excel (`.xlsx`), and LaTeX (`.tex`) files, or URLs, to Markdown, including batch import (`leafpress import *.docx *.tex`). LaTeX support covers multi-file projects, theorems, cross-references, siunitx, and Beamer slides
- **Monorepo support** — combine multiple MkDocs projects into a single document with per-project metadata overrides
- **Mermaid diagrams** — fenced `mermaid` code blocks rendered to images via mermaid.ink or a self-hosted server, or kept as code with `--no-mermaid`
- **Diagram fetching** — pull diagrams from URLs and Lucidchart API with caching, in parallel
- **Safe for untrusted repos** — converting a repository you don't control can't read local files outside it, reach internal hosts, or inject scripts (HTML is sanitized automatically for git URL sources). See [Remote Sources](https://leafpress.dev/remote-sources/#converting-untrusted-repositories)
- Cover page, table of contents, branded footer, and **watermark overlay**
- Logo, colors, and metadata via a simple `leafpress.yml` config
- Git version info (tag, branch, commit) embedded in output — **package version auto-detected** from `pyproject.toml`, `package.json`, `Cargo.toml`, and more
- Convert from **local paths** or **remote git URLs** (including monorepo git URL projects)
- **Actionable error messages** — rendering failures show specific fixes (missing libraries, unsupported image formats)
- **`leafpress doctor`** — diagnose your environment and optional dependencies
- **Desktop UI** — macOS/Linux/Windows menu bar app
- **CI-friendly** — a [GitHub Action](https://leafpress.dev/ci/), a [Docker image](https://leafpress.dev/docker/), and configuration entirely via `LEAFPRESS_*` environment variables

## Installation

```bash
# Base install (DOCX, HTML, ODT, EPUB output + document import)
uv add leafpress
pip install leafpress

# With PDF output (WeasyPrint)
uv add 'leafpress[pdf]'
pip install 'leafpress[pdf]'

# With desktop UI (PyQt6)
uv add 'leafpress[ui]'
pip install 'leafpress[ui]'

# Everything
uv add 'leafpress[all]'
pip install 'leafpress[all]'
```

WeasyPrint requires system libraries on Linux — see [Installation docs](https://leafpress.dev/installation) for details. Run `leafpress doctor` to check your environment.

## Quick Start

```bash
# Generate a starter branding config
leafpress init

# Convert to PDF (auto-detects project in current directory)
leafpress convert

# Convert to PDF + DOCX with branding
leafpress convert /path/to/project -f both -c leafpress.yml

# Convert to EPUB, HTML, ODT, or consolidated Markdown
leafpress convert /path/to/project -f epub
leafpress convert /path/to/project -f html
leafpress convert /path/to/project -f odt
leafpress convert /path/to/project -f markdown

# Convert to all formats (PDF, DOCX, HTML, ODT, EPUB, Markdown)
leafpress convert /path/to/project -f all -c leafpress.yml

# Convert from a remote git repo
leafpress convert https://github.com/org/repo -b main -f pdf

# Import Word, PowerPoint, Excel, or LaTeX documents to Markdown
leafpress import report.docx
leafpress import deck.pptx
leafpress import data.xlsx
leafpress import paper.tex
leafpress import *.docx *.pptx *.xlsx *.tex -o docs/
leafpress import https://example.com/report.docx -o docs/

# Keep mermaid diagrams as code (nothing sent to mermaid.ink)
leafpress convert /path/to/project --no-mermaid

# Check your environment
leafpress doctor

# Show site info (pages, nav, git status)
leafpress info /path/to/project
```

## Desktop UI

```bash
# Launch menu bar / system tray app
leafpress ui

# Open the window immediately on launch
leafpress ui --show
```

On macOS, LeafPress lives in the menu bar (not the Dock). Click the icon to open the conversion window, which covers the common `convert` options (format, branding, cover/TOC, git branch, watermark, mermaid, HTML sanitizing), or the import window for documents. See [Desktop UI](https://leafpress.dev/ui/).

Requires the `[ui]` extra: `pip install 'leafpress[ui]'`

## CI / GitHub Actions

The quickest route is the composite action, which sets up Python and WeasyPrint for you. Pin it to a release tag (or a commit SHA):

```yaml
jobs:
  docs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7

      - uses: hutchins/leafpress@v0.8.3
        with:
          format: pdf
          output: dist
        env:
          LEAFPRESS_COMPANY_NAME: ${{ vars.COMPANY_NAME }}
          LEAFPRESS_PROJECT_NAME: My Project
```

Or install it yourself. LeafPress can be configured entirely via environment variables, with no `leafpress.yml` needed:

```yaml
jobs:
  docs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7

      - name: Install WeasyPrint system dependencies
        run: sudo apt-get install -y libpango-1.0-0 libharfbuzz0b libpangoft2-1.0-0

      - name: Install leafpress
        run: pip install 'leafpress[pdf]'

      - name: Convert docs to PDF
        env:
          LEAFPRESS_COMPANY_NAME: ${{ vars.COMPANY_NAME }}
          LEAFPRESS_PROJECT_NAME: My Project
          LEAFPRESS_PRIMARY_COLOR: "#1a73e8"
        run: leafpress convert . -f pdf -o dist/

      - name: Upload artifact
        uses: actions/upload-artifact@v7
        with:
          name: documentation
          path: dist/*.pdf
```

You can also place a `.env` file in your project root, and LeafPress loads its `LEAFPRESS_*` settings automatically. Shell environment variables always take priority over `.env` values, and a `.env` inside a repository cloned from a git URL is never loaded.

See [CI / GitHub Actions docs](https://leafpress.dev/ci) for the full environment variable reference.

## Branding Configuration

Create `leafpress.yml` in your project root (or run `leafpress init`):

```yaml
company_name: "Acme Corp"
project_name: "Platform Docs"
logo_path: "./logo.png"         # local path or https:// URL
subtitle: "Internal Documentation"
author: "Engineering Team"
primary_color: "#1a73e8"        # 6-digit hex
accent_color: "#ffffff"

watermark:
  text: "DRAFT"                 # optional; also --watermark

mermaid:
  enabled: true                 # false keeps diagrams as code
  server: https://mermaid.ink   # or a self-hosted mermaid.ink

footer:
  include_tag: true
  include_date: true
  include_commit: true
  include_branch: false
  custom_text: "Confidential"

pdf:
  page_size: "A4"
  margin_top: "25mm"
  margin_bottom: "25mm"
  margin_left: "20mm"
  margin_right: "20mm"
```

See [Configuration](https://leafpress.dev/configuration/) for every option.

## Development

```bash
uv sync --group dev
make setup-hooks          # pre-commit: ruff + ty
uv run pytest tests/ -q
uv run ruff check . && uv run ruff format --check .
uvx ty check
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the test layout and how to add renderers and importers. Please report security issues privately as described in [SECURITY.md](SECURITY.md).

### Installing globally from a local checkout

LeafPress requires Python 3.13+. To install as a standalone tool from your local repo:

```bash
uv tool install '/path/to/leafpress[all]' --force --python 3.13
```

If Python 3.13 isn't installed yet, `uv` can fetch it automatically:

```bash
uv python install 3.13
uv tool install '/path/to/leafpress[all]' --force --python 3.13
```

To update after making local changes, uninstall first to avoid caching:

```bash
uv tool uninstall leafpress
uv tool install '/path/to/leafpress[all]' --python 3.13
```

After installation, `leafpress` is available globally — run `leafpress ui --show` from anywhere.
