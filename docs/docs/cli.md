# CLI Reference

## Overview

```
leafpress [OPTIONS] COMMAND [ARGS]...
```

| Command | Description |
|---------|-------------|
| [`convert`](#convert) | Convert an MkDocs site to PDF, DOCX, HTML, ODT, and/or EPUB |
| [`doctor`](#doctor) | Check your environment and optional dependency status |
| [`import`](#import) | Import Word, PowerPoint, or Excel documents to Markdown |
| [`init`](#init) | Generate a starter `leafpress.yml` branding config |
| [`info`](#info) | Display detected MkDocs site info |
| [`fetch-diagrams`](#fetch-diagrams) | Fetch diagrams from external sources (URLs, Lucidchart) |
| [`ui`](#ui) | Launch the desktop menu bar / system tray app |

---

## Global Options

| Option | Description |
|--------|-------------|
| `--version`, `-v` | Show the leafpress version and exit |

---

## `convert`

Convert an MkDocs site to PDF, DOCX, HTML, ODT, and/or EPUB.

```bash
leafpress convert [SOURCE] [OPTIONS]
```

**Arguments**

| Argument | Description |
|----------|-------------|
| `SOURCE` | Path to a local MkDocs project directory, or a git URL. **Optional** — auto-detected if omitted (see [Project Auto-Detection](#project-auto-detection)) |

**Options**

| Option | Default | Description |
|--------|---------|-------------|
| `--output`, `-o` | `output/` | Output directory for generated files |
| `--format`, `-f` | `pdf` | Output format: `pdf`, `docx`, `html`, `odt`, `epub`, `both` (pdf+docx), or `all` |
| `--config`, `-c` | _(auto-detect)_ | Path to `leafpress.yml` branding config |
| `--mkdocs-config` | _(auto-detect)_ | Override path to `mkdocs.yml` |
| `--branch`, `-b` | _(default branch)_ | Git branch to clone (remote sources only) |
| `--cover-page` / `--no-cover-page` | `--cover-page` | Include a cover page |
| `--toc` / `--no-toc` | `--toc` | Include a table of contents |
| `--open` | `false` | Open the generated file(s) after conversion |
| `--local-time` | `false` | Use local timezone for cover page date instead of UTC |
| `--watermark`, `-w` | _(none)_ | Watermark text overlay (e.g. `"DRAFT"`, `"CONFIDENTIAL"`) |
| `--fetch-diagrams` | `false` | Fetch diagrams from external sources before converting |
| `--verbose` | `false` | Show full traceback on error |

**Examples**

```bash
# Auto-detect project and convert to PDF
leafpress convert

# Convert local project to PDF
leafpress convert /path/to/project

# Convert to both PDF and DOCX
leafpress convert /path/to/project -f both

# Convert to HTML, ODT, or EPUB
leafpress convert /path/to/project -f html
leafpress convert /path/to/project -f odt
leafpress convert /path/to/project -f epub

# Convert to all formats (PDF, DOCX, HTML, ODT, EPUB)
leafpress convert /path/to/project -f all

# Convert with branding config, output to custom dir
leafpress convert /path/to/project -c leafpress.yml -o dist/

# Convert from a git URL (specific branch)
leafpress convert https://github.com/org/repo -b main -f pdf

# Use local timezone for the cover page date
leafpress convert . --local-time

# Add a watermark overlay
leafpress convert . -f pdf -w "DRAFT"
leafpress convert . -f all --watermark "CONFIDENTIAL"

# Fetch diagrams before converting
leafpress convert . -c leafpress.yml --fetch-diagrams

# No cover page, open after conversion
leafpress convert . --no-cover-page --open

# Monorepo — combine multiple MkDocs projects into one document
# (requires "projects" in leafpress.yml, see Configuration > Monorepo support)
leafpress convert /path/to/monorepo -c leafpress.yml -f pdf

# Use a specific mkdocs.yml
leafpress convert /path/to/project --mkdocs-config /path/to/docs/mkdocs.yml
```

**Config auto-detection**

leafpress looks for `leafpress.yml` or `leafpress.yaml` in the project root automatically. You only need `--config` if the file is elsewhere.

leafpress also loads a `.env` file from the project root and applies any `LEAFPRESS_*` environment variables on top of the YAML config. See [Configuration](configuration.md#environment-variables).

---

## `doctor`

Check your environment and show the status of optional dependencies. Useful for diagnosing missing system libraries (e.g. WeasyPrint's cairo/pango) or confirming your install is complete.

```bash
leafpress doctor [OPTIONS]
```

**Options**

| Option | Default | Description |
|--------|---------|-------------|
| `--verbose` | `false` | Also check core dependencies (normally guaranteed to be installed) |
| `--debug` | `false` | Show captured error output from failed checks for troubleshooting |

**Checks performed**

| Check | What it verifies |
|-------|-----------------|
| Python version | Python >= 3.13 |
| WeasyPrint | Python package installed (optional — needed for PDF output) |
| WeasyPrint system libs | cairo, pango, gdk-pixbuf C libraries work correctly |
| PyQt6 | Python package installed (optional — needed for desktop UI) |
| pyobjc (macOS only) | Cocoa bindings installed (optional — needed for macOS UI) |

With `--verbose`, all 18 core dependencies are also checked.

**Exit codes**

- `0` — all checks passed
- `1` — one or more checks failed

**Examples**

```bash
# Quick check of optional dependencies
leafpress doctor

# Include core dependency checks
leafpress doctor --verbose

# Show captured stderr from failed checks
leafpress doctor --debug
```

---

## `import`

Import one or more Word or PowerPoint documents and convert them to Markdown.

```bash
leafpress import FILES... [OPTIONS]
```

**Arguments**

| Argument | Description |
|----------|-------------|
| `FILES...` | One or more `.docx` or `.pptx` files to import. You can mix formats in a single command. |

**Options**

| Option | Default | Description |
|--------|---------|-------------|
| `--output`, `-o` | `<stem>.md` | Output `.md` file path or directory. Must be a directory when importing multiple files. |
| `--extract-images` / `--no-extract-images` | `--extract-images` | Extract embedded images to an `assets/` folder |
| `--code-styles` | _(none)_ | Comma-separated Word style names to treat as code blocks (DOCX only) |
| `--notes` / `--no-notes` | `--notes` | Include speaker notes as blockquotes (PPTX only) |

**Examples**

```bash
# Import a single Word document (creates report.md alongside report.docx)
leafpress import report.docx

# Import a PowerPoint presentation
leafpress import deck.pptx

# Import multiple files at once
leafpress import report.docx deck.pptx notes.docx

# Import all Word and PowerPoint files in a directory
leafpress import *.docx *.pptx

# Output all results to a directory
leafpress import *.docx *.pptx -o docs/

# Import PPTX without speaker notes
leafpress import deck.pptx --no-notes

# Specify output path for a single file
leafpress import report.docx -o docs/report.md

# Skip image extraction
leafpress import deck.pptx --no-extract-images

# Treat custom Word styles as code blocks
leafpress import report.docx --code-styles "Code Block,Source Code"
```

---

## `init`

Generate a starter `leafpress.yml` branding config file.

```bash
leafpress init [PATH]
```

**Arguments**

| Argument | Default | Description |
|----------|---------|-------------|
| `PATH` | `.` | Directory to create the config file in |

**Example**

```bash
leafpress init
# Creates ./leafpress.yml

leafpress init /path/to/project
# Creates /path/to/project/leafpress.yml
```

---

## `info`

Display detected MkDocs site info: navigation structure, markdown extensions, and git information.

```bash
leafpress info [SOURCE] [OPTIONS]
```

**Arguments**

| Argument | Description |
|----------|-------------|
| `SOURCE` | Path to a local MkDocs directory or git URL. **Optional** — auto-detected if omitted (see [Project Auto-Detection](#project-auto-detection)) |

**Options**

| Option | Description |
|--------|-------------|
| `--branch`, `-b` | Git branch (for remote git URLs) |

**Example**

```bash
# Auto-detect project
leafpress info

# Explicit path
leafpress info /path/to/project
leafpress info https://github.com/org/repo -b main
```

---

## `fetch-diagrams`

Fetch diagrams from external sources (URLs, Lucidchart API) defined in your `leafpress.yml` config.

```bash
leafpress fetch-diagrams [OPTIONS]
```

**Options**

| Option | Default | Description |
|--------|---------|-------------|
| `--config`, `-c` | _(auto-detect)_ | Path to `leafpress.yml` config file |
| `--refresh` | `false` | Force re-download even if cached files exist |
| `--verbose` | `false` | Show full traceback on error |

**Examples**

```bash
# Fetch using auto-detected leafpress.yml
leafpress fetch-diagrams

# Specify a config file
leafpress fetch-diagrams -c path/to/leafpress.yml

# Force re-download, ignoring cache
leafpress fetch-diagrams --refresh
```

See [Diagrams](diagrams.md) for full configuration and usage details.

---

## `ui`

Launch the leafpress menu bar / system tray desktop application.

```bash
leafpress ui [OPTIONS]
```

**Options**

| Option | Default | Description |
|--------|---------|-------------|
| `--show` | `false` | Open the conversion window immediately on launch |

**Example**

```bash
leafpress ui
leafpress ui --show
```

Requires the `[ui]` extra. See [Desktop UI](ui.md) for installation and usage details.

---

## Project Auto-Detection

When `SOURCE` is omitted from `convert` or `info`, leafpress automatically searches for an MkDocs project:

**Search order:**

1. **Git repo root** — if you're inside a git repository, leafpress checks the repo root for `mkdocs.yml`
2. **Git root / `docs/`** — checks a `docs/` subdirectory of the repo root
3. **Current directory** — falls back to CWD if not in a git repo
4. **CWD / `docs/`** — checks a `docs/` subdirectory of CWD

The first directory containing `mkdocs.yml` (or `mkdocs.yaml`) is used.

**Examples**

```bash
# Inside a git repo with mkdocs.yml at root
cd ~/projects/my-docs
leafpress convert -f pdf

# Inside a git repo with mkdocs.yml in docs/
cd ~/projects/my-app
leafpress convert -f all -o dist/

# Not in a git repo — uses CWD
cd /tmp/some-docs
leafpress info
```

If no `mkdocs.yml` is found, leafpress exits with an error and suggests specifying the path explicitly.
