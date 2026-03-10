# CLI Reference

## Overview

```
leafpress [OPTIONS] COMMAND [ARGS]...
```

| Command | Description |
|---------|-------------|
| [`convert`](#convert) | Convert an MkDocs site to PDF, DOCX, HTML, ODT, and/or EPUB |
| [`doctor`](#doctor) | Check your environment and optional dependency status |
| [`import`](#import) | Import a Word document and convert it to Markdown |
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
leafpress convert SOURCE [OPTIONS]
```

**Arguments**

| Argument | Description |
|----------|-------------|
| `SOURCE` | Path to a local MkDocs project directory, or a git URL |

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

# Use a specific mkdocs.yml (monorepo)
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
```

---

## `import`

Import a Word document and convert it to Markdown.

```bash
leafpress import DOCX_FILE [OPTIONS]
```

**Arguments**

| Argument | Description |
|----------|-------------|
| `DOCX_FILE` | Path to the `.docx` file to import |

**Options**

| Option | Default | Description |
|--------|---------|-------------|
| `--output`, `-o` | `<docx-stem>.md` | Output `.md` file path or directory |
| `--extract-images` / `--no-extract-images` | `--extract-images` | Extract embedded images to an `assets/` folder |
| `--code-styles` | _(none)_ | Comma-separated Word style names to treat as code blocks |

**Examples**

```bash
# Import a Word document to Markdown (creates report.md alongside report.docx)
leafpress import report.docx

# Specify output path
leafpress import report.docx -o docs/report.md

# Output to a directory (creates dir/report.md)
leafpress import report.docx -o docs/

# Skip image extraction
leafpress import report.docx --no-extract-images

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
leafpress info SOURCE [OPTIONS]
```

**Arguments**

| Argument | Description |
|----------|-------------|
| `SOURCE` | Path to a local MkDocs directory or git URL |

**Options**

| Option | Description |
|--------|-------------|
| `--branch`, `-b` | Git branch (for remote git URLs) |

**Example**

```bash
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
