# Changelog

## 0.2.0 — 2026-03-10

### Features

- **EPUB output format** — new `leafpress convert -f epub` produces reflowable e-books via ebooklib, with cover page, table of contents, branding CSS, and watermark support
- **DOCX → Markdown import** — new `leafpress import` command converts Word documents to Markdown using mammoth + markdownify, with image extraction, custom code-style mapping, and pipe tables
- **Optional PDF extras** — WeasyPrint moved from base dependency to `leafpress[pdf]`; base install (`pip install leafpress`) no longer requires system libraries
  - `leafpress[pdf]` — adds PDF output (WeasyPrint)
  - `leafpress[ui]` — adds desktop UI (PyQt6)
  - `leafpress[all]` — everything

### Improvements

- Lazy renderer imports in pipeline — `leafpress --help` and non-PDF commands work without WeasyPrint system libraries installed
- Friendly error message when PDF output is requested without `leafpress[pdf]`
- `convert -f all` now generates 5 formats (PDF, DOCX, HTML, ODT, EPUB)

### Tests

- 21 new EPUB renderer tests (cover page, TOC, chapter splitting, branding, watermarks, metadata)
- 23 new DOCX import tests (headings, formatting, lists, tables, images, code blocks, pipe tables, CLI integration)
- 291 total tests, 91% coverage

### Docs

- New [EPUB](epub.md) documentation page with format details and examples
- [Installation](installation.md) restructured with extras: base, `[pdf]`, `[ui]`, `[all]`
- CLI, CI/CD, and homepage updated to include EPUB format
- Dockerfile updated with `--extra pdf` for optional dependency
- GitHub Action updated to install `leafpress[pdf]`

---

## 0.1.3 — 2026-03-10

### Features

- `leafpress fetch-diagrams` command to pull diagrams from URLs and Lucidchart API
- `--fetch-diagrams` flag on `convert` command to fetch diagrams as a pre-step
- `diagrams` config section in `leafpress.yml` with caching, Lucidchart token, and source list
- `LEAFPRESS_LUCIDCHART_TOKEN` environment variable for secure token configuration

### Tests

- 17 new DOCX HTML converter tests (strikethrough, superscript, subscript, highlight, line break, task lists, nested lists, images, emoji) — coverage from 90% to 99%
- 30 new diagram tests (config models, cache staleness, URL/Lucidchart fetch, CLI commands)
- Fixed internal link checker to skip fenced code blocks

### Docs

- New [Diagrams](diagrams.md) documentation page with configuration, CLI usage, Lucidchart setup, caching, and CI/CD examples
- Diagram Fetching feature card on homepage
- CLI reference updated with `fetch-diagrams` command and `--fetch-diagrams` flag
- Configuration page updated with `diagrams` section and field reference
- CI/CD page updated with diagram fetching examples and `LEAFPRESS_LUCIDCHART_TOKEN`

---

## 0.1.2 — 2026-03-10

### Features

- Docker support with multi-stage build (Dockerfile, .dockerignore, docs page)
- `--version` flag documented in CLI reference

### Fixes

- Fixed DOCX watermark rendering (VML namespace registration)

### Tests

- Added 36 new tests bringing coverage from 87% to 91%
- Added optional Docker integration tests (`pytest -m docker`)
- New test files: `test_main.py`, `test_init.py`
- Expanded: `test_source.py`, `test_cli.py`, `test_git_info.py`, `test_docx_renderer.py`, `test_odt_renderer.py`

### Docs

- Added Docker documentation page and feature card on homepage
- Added Global Options section to CLI reference

---

## 0.1.1 — 2026-03-10

### Features

- HTML single-file output format
- ODT (OpenDocument Text) output format
- `--local-time` CLI flag to use local timezone for cover page dates (default: UTC)
- `leafpress convert -f all` generates all four formats in one run
- Improved `leafpress ui` error message with install commands for uv, pip, and pipx
- Watermark overlay support (`--watermark` CLI flag or `watermark` config section)

### Improvements

- Single-source version via `importlib.metadata` (only edit `pyproject.toml` to bump)
- GitHub Action updated with `html`, `odt`, and `all` format options and `local_time` input
- Desktop UI includes "Use local timezone for dates" checkbox

### Tests

- Added 68 new tests (pipeline, DOCX converter, PDF/HTML/DOCX styles, security)
- YAML deserialization safety tests (safe_load enforcement, tag neutralization)
- Path traversal tests for `logo_path` and `template_path`

### Docs

- All documentation pages updated for HTML and ODT support
- CLI reference updated with `--local-time` flag and new format options
- CI page updated with new action inputs and environment variables
- Fixed tab rendering in docs (added `pymdownx.tabbed` extension)

---

## 0.1.0 — 2026-03-09

Initial release.

### Features

- Convert MkDocs sites to PDF (WeasyPrint) and DOCX (python-docx)
- Branded cover page, table of contents, and footer
- Git version info embedded in output (tag, commit, date, branch)
- `leafpress.yml` branding config
- `LEAFPRESS_*` environment variable overrides with `.env` support
- Remote git URL sources
- Desktop UI (PyQt6 menu bar / system tray app)
- Composite GitHub Action (`uses: hutchins/leafpress@main`)
- "Made with LeafPress" attribution in all rendered footers
