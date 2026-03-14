# Configuration

LeafPress branding is configured via a `leafpress.yml` file in your project root, environment variables, or a `.env` file.

## Generating a starter config

```bash
leafpress init
```

This creates a `leafpress.yml` in the current directory with all available fields commented.

## Full configuration reference

```yaml
# leafpress.yml

# Required (if using YAML config)
company_name: "Acme Corp"
project_name: "Platform Docs"

# Optional metadata
logo_path: "./logo.png"         # local path (relative to this file) or https:// URL
subtitle: "Internal Documentation"
author: "Engineering Team"
author_email: "team@example.com"
document_owner: "Jane Smith"    # shown on cover page
review_cycle: "Quarterly"       # shown on cover page
copyright_text: "Copyright © 2026 Acme Corp"

# Colors (6-digit hex)
primary_color: "#1a73e8"        # default: #1a73e8
accent_color: "#ffffff"          # default: #ffffff

# Footer options
footer:
  include_tag: true             # show git tag in footer (default: true)
  include_date: true            # show build date (default: true)
  include_commit: true          # show commit hash (default: true)
  include_branch: false         # show branch name (default: false)
  include_render_date: false    # append generation date to footer
  custom_text: "Confidential"   # optional static footer text
  repo_url: "https://github.com/org/repo"  # link in footer

# PDF-specific options
pdf:
  page_size: "A4"               # A4 or Letter (default: A4)
  margin_top: "25mm"
  margin_bottom: "25mm"
  margin_left: "20mm"
  margin_right: "20mm"

# DOCX-specific options
docx:
  template_path: null           # path to a .docx template file

# Watermark overlay
watermark:
  text: "DRAFT"                 # set to null or remove to disable
  color: "#cccccc"              # watermark text color
  opacity: 0.15                 # 0.0 to 1.0
  angle: -45                    # -90 to 90
```

## Diagrams

See the dedicated [Diagrams](diagrams.md) page for full usage details. Below is the config reference.

```yaml
# Diagram fetching (optional)
diagrams:
  cache_max_age: 3600           # seconds; 0 = always re-download
  lucidchart_token: null        # or set LEAFPRESS_LUCIDCHART_TOKEN env var
  sources:
    - url: https://example.com/architecture.svg
      dest: docs/assets/diagrams/architecture.svg
    - lucidchart: abc123-document-id
      dest: docs/assets/diagrams/network.png
      page: 1
```

## Field reference

### Top-level fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `company_name` | string | — | Company or organization name (required) |
| `project_name` | string | — | Project or document title (required) |
| `logo_path` | string | `null` | Path to logo image or `https://` URL (PNG/JPEG recommended; SVG works in PDF/HTML but not DOCX/ODT) |
| `subtitle` | string | `null` | Subtitle shown on cover page |
| `author` | string | `null` | Author name |
| `author_email` | string | `null` | Author email |
| `document_owner` | string | `null` | Document owner shown on cover page |
| `review_cycle` | string | `null` | Review cycle shown on cover page (e.g. "Quarterly") |
| `copyright_text` | string | `null` | Copyright line on cover page |
| `primary_color` | hex string | `#1a73e8` | Primary brand color (6-digit hex) |
| `accent_color` | hex string | `#ffffff` | Accent/background color (6-digit hex) |

### `footer` fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `include_tag` | bool | `true` | Include git tag in footer |
| `include_date` | bool | `true` | Include build date |
| `include_commit` | bool | `true` | Include short commit hash |
| `include_branch` | bool | `false` | Include branch name |
| `include_render_date` | bool | `false` | Append document generation date to footer |
| `custom_text` | string | `null` | Static text appended to footer |
| `repo_url` | string | `null` | Repository URL linked in footer |

### `pdf` fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `page_size` | string | `A4` | Page size (`A4` or `Letter`) |
| `margin_top` | string | `25mm` | Top margin |
| `margin_bottom` | string | `25mm` | Bottom margin |
| `margin_left` | string | `20mm` | Left margin |
| `margin_right` | string | `20mm` | Right margin |

### `docx` fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `template_path` | path | `null` | Path to a `.docx` template file |

### `watermark` fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `text` | string | `null` | Watermark text (e.g. `"DRAFT"`, `"CONFIDENTIAL"`) — `null` to disable |
| `color` | hex string | `#cccccc` | Watermark text color |
| `opacity` | float | `0.15` | Opacity from `0.0` (invisible) to `1.0` (solid) |
| `angle` | int | `-45` | Rotation angle from `-90` to `90` degrees |

### `diagrams` fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `cache_max_age` | int | `3600` | Seconds before a cached diagram is considered stale |
| `lucidchart_token` | string | `null` | Lucidchart API token (prefer `LEAFPRESS_LUCIDCHART_TOKEN` env var) |
| `sources` | list | `[]` | List of diagram sources to fetch |

### `diagrams.sources[]` fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `url` | string | `null` | HTTP/HTTPS URL to download |
| `lucidchart` | string | `null` | Lucidchart document ID to export as PNG |
| `dest` | string | _(required)_ | Local path to save the file (relative to config) |
| `page` | int | `1` | Page number to export (Lucidchart only) |

## Monorepo support

When your documentation spans multiple MkDocs projects (e.g. a monorepo with separate services), you can list them in `leafpress.yml` under the `projects` key. LeafPress renders them as chapters of a single combined document with one cover page and one unified table of contents.

### Basic usage

```yaml
# leafpress.yml
company_name: "Acme Corp"
project_name: "Platform Documentation"

projects:
  - services/api
  - services/frontend
  - shared/docs
```

Each entry is a path (relative to the config file) to a directory containing its own `mkdocs.yml`.

### Git URL projects

Projects can also reference remote git repositories. LeafPress clones them automatically during conversion.

```yaml
projects:
  # Local path
  - services/api

  # Git URL
  - url: https://github.com/org/frontend-docs
    branch: main
    author: "Frontend Team"

  # Mix of local and remote
  - path: shared/docs
  - url: git@github.com:org/api-docs.git
    document_owner: "API Team"
```

Each URL entry supports an optional `branch` field. If omitted, the default branch is used. Cloned repos are cleaned up automatically after conversion.

### Per-project metadata

Each project can override metadata fields that appear under its chapter heading. Fields not set on the project inherit from the top-level branding config.

```yaml
company_name: "Acme Corp"
project_name: "Platform Documentation"
author: "Engineering"              # default for all projects

projects:
  - path: services/api
    author: "API Team"
    document_owner: "Jane Smith"
    review_cycle: "Monthly"
  - path: services/frontend
    author: "Frontend Team"
    document_owner: "Bob Jones"
    subtitle: "React Component Library"
  - path: shared/docs
    # inherits top-level author "Engineering"
```

**Available per-project overrides:**

| Field | Description |
|-------|-------------|
| `path` | Local directory containing `mkdocs.yml` (use `path` **or** `url`) |
| `url` | Git URL to clone (use `path` **or** `url`) |
| `branch` | Git branch to checkout (`url` projects only) |
| `author` | Author name for this chapter |
| `author_email` | Author email for this chapter |
| `document_owner` | Document owner for this chapter |
| `review_cycle` | Review cycle for this chapter |
| `subtitle` | Subtitle shown under the chapter heading |

### How it renders

Each project becomes a top-level chapter in the output. The project's `site_name` (from its `mkdocs.yml`) is used as the chapter title. All pages within a project are nested one level deeper.

```
┌──────────────────────────────┐
│ Acme Corp                    │  ← cover page (top-level branding)
│ Platform Documentation       │
│ Author: Engineering          │
├──────────────────────────────┤
│ Table of Contents            │  ← unified TOC
│ 1. API Service               │
│    1.1 Overview              │
│    1.2 Endpoints             │
│ 2. Frontend App              │
│    2.1 Getting Started       │
│    2.2 Components            │
├──────────────────────────────┤
│ API Service                  │  ← chapter heading
│ Author: API Team             │
│ Document Owner: Jane Smith   │
│                              │
│   Overview                   │  ← project pages (nested)
│   ...                        │
├──────────────────────────────┤
│ Frontend App                 │  ← chapter heading
│ Author: Frontend Team        │
│   Getting Started            │
│   ...                        │
└──────────────────────────────┘
```

!!! note
    When `projects` is defined, the top-level `mkdocs.yml` in the config directory is **not** used. Each project must have its own `mkdocs.yml`.

## Environment variables

All config fields can be set or overridden via `LEAFPRESS_*` environment variables. This is the recommended approach for CI/CD pipelines.

**Priority order:** shell env > `.env` file > `leafpress.yml` > built-in defaults

| Environment variable | Config field |
|----------------------|-------------|
| `LEAFPRESS_COMPANY_NAME` | `company_name` |
| `LEAFPRESS_PROJECT_NAME` | `project_name` |
| `LEAFPRESS_LOGO_PATH` | `logo_path` |
| `LEAFPRESS_SUBTITLE` | `subtitle` |
| `LEAFPRESS_AUTHOR` | `author` |
| `LEAFPRESS_AUTHOR_EMAIL` | `author_email` |
| `LEAFPRESS_DOCUMENT_OWNER` | `document_owner` |
| `LEAFPRESS_REVIEW_CYCLE` | `review_cycle` |
| `LEAFPRESS_COPYRIGHT_TEXT` | `copyright_text` |
| `LEAFPRESS_PRIMARY_COLOR` | `primary_color` |
| `LEAFPRESS_ACCENT_COLOR` | `accent_color` |
| `LEAFPRESS_FOOTER_CUSTOM_TEXT` | `footer.custom_text` |
| `LEAFPRESS_FOOTER_REPO_URL` | `footer.repo_url` |
| `LEAFPRESS_FOOTER_INCLUDE_TAG` | `footer.include_tag` (`true`/`false`) |
| `LEAFPRESS_FOOTER_INCLUDE_DATE` | `footer.include_date` |
| `LEAFPRESS_FOOTER_INCLUDE_COMMIT` | `footer.include_commit` |
| `LEAFPRESS_FOOTER_INCLUDE_BRANCH` | `footer.include_branch` |
| `LEAFPRESS_FOOTER_INCLUDE_RENDER_DATE` | `footer.include_render_date` |
| `LEAFPRESS_LOCAL_TIME` | Use local timezone for dates (`true`/`false`, default: `false`) |
| `LEAFPRESS_WATERMARK_TEXT` | `watermark.text` |
| `LEAFPRESS_WATERMARK_COLOR` | `watermark.color` |
| `LEAFPRESS_WATERMARK_OPACITY` | `watermark.opacity` (e.g. `0.2`) |
| `LEAFPRESS_WATERMARK_ANGLE` | `watermark.angle` (e.g. `-30`) |
| `LEAFPRESS_LUCIDCHART_TOKEN` | `diagrams.lucidchart_token` |

!!! tip "Env-only mode"
    If both `LEAFPRESS_COMPANY_NAME` and `LEAFPRESS_PROJECT_NAME` are set and no `leafpress.yml` is present, LeafPress builds the branding config entirely from environment variables.

## `.env` file support

LeafPress automatically loads a `.env` file from the project root before applying config. Shell environment variables always override `.env` values.

```bash
# .env
LEAFPRESS_COMPANY_NAME=Acme Corp
LEAFPRESS_PROJECT_NAME=Platform Docs
LEAFPRESS_PRIMARY_COLOR=#1a73e8
```

See [CI / GitHub Actions](ci.md) for pipeline-specific guidance.
