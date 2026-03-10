# Changelog

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
