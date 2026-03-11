# Changelog

## 0.4.0 — 2026-03-11

### Features

- **Monorepo support** — list multiple MkDocs projects in `leafpress.yml` under `projects`; each project renders as a chapter of a single combined document with one cover page and unified TOC; per-project metadata overrides (author, document_owner, review_cycle, subtitle); supports git URL projects with optional branch
- **PowerPoint import** — `leafpress import deck.pptx` converts presentations to Markdown; slide titles become H2 headings, speaker notes render as blockquotes, tables and images are extracted; `--notes/--no-notes` flag to toggle speaker notes
- **Multi-file import** — `leafpress import *.docx *.pptx` processes multiple files in one command with mixed format support and partial failure handling
- **`review_cycle` config field** — new optional field displayed on cover page of all output formats; configurable via `LEAFPRESS_REVIEW_CYCLE` env var

### Tests

- 19 new PPTX import tests (slides, formatting, tables, images, notes, CLI integration)
- 17 new monorepo tests (page collection, chapter headings, nav bumping, per-project metadata, config normalization)
- 5 new multi-file import CLI tests (multiple DOCX, mixed formats, output validation, partial failure, backwards compat)
- 3 new dotenv loading tests
- 2 new `bump_nav_levels` tests
- 3 new `review_cycle` config tests
- 444 total tests

### Docs

- New [Document Import](import.md) page with supported/unsupported feature tables for Word and PowerPoint
- New [Architecture](architecture.md) page with pipeline flowcharts, module map, and key dependencies
- [Configuration](configuration.md) updated with monorepo support section and `review_cycle` field
- [CLI reference](cli.md) updated with multi-file import, PPTX support, monorepo example, and `--notes` flag
- [About](about.md) updated with source control migration messaging

---

## 0.3.0 — 2026-03-10

### Features

- **Project auto-detection** — `leafpress convert` and `leafpress info` now auto-detect the MkDocs project directory when no `source` argument is given; searches git root, `docs/` subdirectory, CWD, and `CWD/docs/` in order
- **`document_owner` config field** — new optional field in `leafpress.yml` displayed on the cover page of all output formats (PDF, HTML, EPUB, DOCX, ODT); also configurable via `LEAFPRESS_DOCUMENT_OWNER` env var
- **Mermaid diagram rendering** — fenced `mermaid` code blocks are rendered as inline SVG diagrams in all output formats
- **Annotation support** — Material for MkDocs-style annotations (`(1)`, `(2)`, etc.) are rendered as numbered footnotes
- `--debug` flag on `leafpress doctor` for detailed diagnostic output

### Tests

- 18 new project auto-detection tests (git root, docs subdir, CWD fallback, yaml extension, error cases)
- 3 new `document_owner` config tests (YAML loading, env override, env-over-YAML precedence)
- 390 total tests

### Docs

- New [Markdown Extensions](extensions.md) page documenting mermaid, annotations, admonitions, tabs, and task lists
- [CLI reference](cli.md) updated with auto-detection behavior, search order, and examples
- [Configuration](configuration.md) updated with `document_owner` field and `LEAFPRESS_DOCUMENT_OWNER` env var

---

## 0.2.2 — 2026-03-10

### Features

- **`leafpress doctor` command** — diagnose your environment with a single command; checks Python version, WeasyPrint (package + system libs), PyQt6, and pyobjc; shows ✓/✗ status, versions, and suggested fixes for any missing dependencies
- `--verbose` flag on `doctor` to also check all 18 core dependencies

### Fixes

- **Properly fixed Rich markup swallowing `[pdf]`/`[ui]` in error messages** — all `console.print()` error sites now use `rich.markup.escape()` instead of embedding Rich-specific escapes in exception messages
- Error messages for missing WeasyPrint now suggest running `leafpress doctor` to diagnose
- **GitHub Releases now auto-created** when tags are pushed — `release.yml` updated with `gh release create` step and `contents: write` permission

### Tests

- 25 new doctor command tests (dataclasses, check functions, orchestrator, CLI integration, Rich escape regression)

### Docs

- New [`doctor`](cli.md#doctor) section in CLI reference with checks table, exit codes, and examples

---

## 0.2.1 — 2026-03-10

### Fixes

- Fixed `[pdf]` being swallowed by Rich markup in the WeasyPrint missing error message — users now correctly see `pip install 'leafpress[pdf]'`

---

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
