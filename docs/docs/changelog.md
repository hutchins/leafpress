# Changelog

## 0.8.0 — 2026-04-04

### Features

- **LaTeX import** — new `leafpress import paper.tex` converter using pylatexenc AST walker, supporting sections, formatting, math passthrough, lists, tables, figures, code blocks, links, footnotes, and image extraction. 14 known limitations documented.
- **URL import** — `leafpress import https://example.com/report.docx` downloads and converts in one step, with Content-Type fallback for extensionless URLs and automatic temp cleanup. Works for all four formats.
- **PPTX warnings** — charts, embedded OLE objects, media, and linked objects now produce warnings identifying the slide and shape name instead of being silently skipped
- **XLSX warnings** — merged cells (with region count), embedded images, embedded charts, and blank workbooks now produce warnings instead of silent data loss
- **Improved warning display** — import CLI now shows up to 10 warnings with ⚠ prefix and a "… and N more" truncation indicator

### Refactor

- **Shared importer base** — extracted `ImportResult`, `resolve_output_path`, `postprocess_markdown`, and `rows_to_pipe_table` from the DOCX converter into `importer/base.py`, eliminating cross-converter import dependencies
- **Shared test helper** — consolidated 4 duplicate `_make_png()` implementations into `tests/helpers.py`
- **Fixed `tabular*` regex** — environments with multiple brace arguments now parse correctly

### Docs

- [Import](import.md) — full LaTeX section with features table, 14-item limitations table, URL import section, and updated batch import examples
- [CLI](cli.md) — updated argument description, added URL and LaTeX examples
- [Architecture](architecture.md) — added LaTeX import section, updated pipeline diagram and module map
- [About](about.md), [Home](index.md), [UI](ui.md) — updated to reflect LaTeX and URL support

### Tests

- 713 total tests (up from 644), 93% importer coverage
- Comprehensive programmatic fixtures for DOCX, PPTX, XLSX, and LaTeX
- Academic paper fixture (`academic_paper.tex`) with 29 assertions
- 8 URL import tests with mocked HTTP
- Edge case tests for LaTeX macros, environments, images, and error paths

---

## 0.7.0 — 2026-03-31

### Features

- **Asset validation warnings** — missing image references are now detected during rendering and reported as warnings with the page name and path, instead of silently producing blank spots in output
- **Consistent error messages** — DOCX, HTML, ODT, and EPUB rendering failures now show format-specific actionable guidance following the "what happened → why → how to fix" pattern (matching the existing PDF error messages)
- **Louder extension load failures** — when a Markdown extension fails to load, the error message is now displayed along with an install suggestion (e.g. `pip install pymdownx`) for missing packages
- **Mermaid cache integrity** — cached mermaid diagram PNGs are now validated by checking PNG magic bytes; corrupted files (truncated writes, disk errors) are automatically re-rendered instead of silently producing broken images
- **Mermaid sanitization refactor** — the mermaid source sanitization pipeline is now split into three named, independently testable helpers: `_unescape_html_entities`, `_replace_literal_backslash_n`, and `_replace_newlines_in_quoted_labels`

### Docs

- [Configuration](configuration.md) — added "How navigation levels work" and "Troubleshooting monorepo builds" sections explaining heading level bumping and common error scenarios
- [Architecture](architecture.md) — added "Monorepo Pipeline" section describing per-project processing, nav level bumping, and chapter cover generation
- [Extensions](extensions.md) — added "Troubleshooting extension failures" section with common fixes
- [CLI](cli.md) — updated verbose output description to reflect new warning details
- [Diagrams](diagrams.md) — added "Mermaid diagram caching" section explaining content-addressed caching and integrity validation

### Tests

- 27 new tests: asset validation tracking (4), extension error message capture (2), error formatter tests for DOCX (2), HTML (3), ODT (2), EPUB (3), PNG validation (4), cache integrity (2), sanitization helpers (6)
- 571 total tests

---

## 0.6.2 — 2026-03-28

### Refactor

- **BaseRenderer protocol and shared helpers** — extracted `replace_checkboxes()`, `make_anchor_id()`, and `resolve_logo_uri()` from PDF, HTML, and EPUB renderers into a new `base_renderer.py` module, eliminating ~90 lines of duplicated code across renderers
- **Normalized checkbox CSS classes** — PDF renderer now uses `.task-checkbox.checked` class naming consistent with HTML and EPUB renderers

### Docs

- [Architecture](architecture.md) — added BaseRenderer protocol and shared helpers section, updated module map and "Adding a New Output Format" guide

---

## 0.5.1 — 2026-03-13

### Fixes

- **DOCX watermark — Google Workspace compatibility** — `v:shapetype` definition is now emitted before the `v:shape` that references it; without it the OOXML was technically invalid and Google Docs rejected the file entirely. Affects users with `watermark.text` set in `leafpress.yml`
- **macOS PDF — WeasyPrint system library detection** — `leafpress doctor` now checks each required library (`cairo`, `pango`, `gdk-pixbuf`, `libffi`) individually and reports the resolved path or a targeted install hint; Apple Silicon users also get a `DYLD_LIBRARY_PATH` hint when libraries are installed but not found
- **macOS PDF — clearer error messages** — `ImportError` (WeasyPrint not installed) and `OSError` (system libs missing) are now handled separately with distinct, actionable messages; the `OSError` path explicitly warns that `brew install weasyprint` is the wrong command

### Docs

- [Installation](installation.md) — replaced `brew install pango` with full macOS instructions (Apple Silicon / Intel tabs, `DYLD_LIBRARY_PATH` tip, warning against `brew install weasyprint`)
- [PDF](pdf.md) — added macOS callout with correct brew packages and `leafpress doctor` pointer
- [DOCX](docx.md) — added Google Workspace compatibility note

---

## 0.5.0 — 2026-03-11

### Features

- **Footer render date** — new `include_render_date` option appends the document generation date to the footer across all output formats; configurable via `leafpress.yml`, `--footer-date` / `--no-footer-date` CLI flags, or `LEAFPRESS_FOOTER_INCLUDE_RENDER_DATE` env var
- **SVG logo validation** — DOCX and ODT renderers now detect SVG logos and skip them with a clear warning instead of crashing; PDF and HTML continue to support SVG natively
- **Actionable PDF error messages** — rendering failures (e.g. `UnrecognizedImageError`) now show specific troubleshooting steps: install librsvg, convert SVG to PNG, or run `leafpress doctor`
- **Pipeline warnings surfaced to console** — `logger.warning()` calls from renderers (SVG logo skip, extension load failures, image embed errors) are now automatically displayed in CLI output as yellow ⚠ messages; `--verbose` additionally surfaces DEBUG-level detail
- **Mermaid diagram progress** — each page with mermaid diagrams now reports a rendered count (e.g. "Rendered 3 mermaid diagram(s) in overview.md") with failure details if any diagrams fail

### Fixes

- **Mermaid `\n` rendering** — literal `\n` text in mermaid diagram labels is now automatically converted to `<br/>` line breaks; actual newlines inside quoted labels are also handled
- **DOCX image embed warnings** — `warnings.warn()` calls in the DOCX HTML converter are now routed through the standard logger so they appear in CLI output

### Tests

- 26 new tests: `_format_pdf_error` error message branches (3), `_is_svg` detection for DOCX (7) and ODT (5), SVG logo skip integration for DOCX (1) and ODT (1), PDF `RenderError` wrapping (1), `_ConsoleWarningHandler` (3), pipeline verbose param (1), mermaid diagram count summary (4)
- 526 total tests

### Docs

- [Configuration](configuration.md) updated with `include_render_date` field, env var, and SVG logo compatibility note
- [Branding](branding.md) updated with SVG logo warning, render date footer option, and CLI override
- [CLI reference](cli.md) updated with `--footer-date` / `--no-footer-date` flag, and `--verbose` description
- [PDF](pdf.md) page updated with new Troubleshooting section for image errors
- [DOCX](docx.md) and [ODT](odt.md) pages updated with SVG limitations
- [Extensions](extensions.md) updated with mermaid line break tip

---

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
