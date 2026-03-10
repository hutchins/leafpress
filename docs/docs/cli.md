# CLI Reference

## Overview

```
leafpress [OPTIONS] COMMAND [ARGS]...
```

| Command | Description |
|---------|-------------|
| [`convert`](#convert) | Convert an MkDocs site to PDF, DOCX, HTML, and/or ODT |
| [`init`](#init) | Generate a starter `leafpress.yml` branding config |
| [`info`](#info) | Display detected MkDocs site info |
| [`ui`](#ui) | Launch the desktop menu bar / system tray app |

---

## `convert`

Convert an MkDocs site to PDF, DOCX, HTML, and/or ODT.

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
| `--format`, `-f` | `pdf` | Output format: `pdf`, `docx`, `html`, `odt`, `both` (pdf+docx), or `all` |
| `--config`, `-c` | _(auto-detect)_ | Path to `leafpress.yml` branding config |
| `--mkdocs-config` | _(auto-detect)_ | Override path to `mkdocs.yml` |
| `--branch`, `-b` | _(default branch)_ | Git branch to clone (remote sources only) |
| `--cover-page` / `--no-cover-page` | `--cover-page` | Include a cover page |
| `--toc` / `--no-toc` | `--toc` | Include a table of contents |
| `--open` | `false` | Open the generated file(s) after conversion |
| `--local-time` | `false` | Use local timezone for cover page date instead of UTC |
| `--verbose` | `false` | Show full traceback on error |

**Examples**

```bash
# Convert local project to PDF
leafpress convert /path/to/project

# Convert to both PDF and DOCX
leafpress convert /path/to/project -f both

# Convert to HTML or ODT
leafpress convert /path/to/project -f html
leafpress convert /path/to/project -f odt

# Convert to all formats (PDF, DOCX, HTML, ODT)
leafpress convert /path/to/project -f all

# Convert with branding config, output to custom dir
leafpress convert /path/to/project -c leafpress.yml -o dist/

# Convert from a git URL (specific branch)
leafpress convert https://github.com/org/repo -b main -f pdf

# Use local timezone for the cover page date
leafpress convert . --local-time

# No cover page, open after conversion
leafpress convert . --no-cover-page --open

# Use a specific mkdocs.yml (monorepo)
leafpress convert /path/to/project --mkdocs-config /path/to/docs/mkdocs.yml
```

**Config auto-detection**

leafpress looks for `leafpress.yml` or `leafpress.yaml` in the project root automatically. You only need `--config` if the file is elsewhere.

leafpress also loads a `.env` file from the project root and applies any `LEAFPRESS_*` environment variables on top of the YAML config. See [Configuration](configuration.md#environment-variables).

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
