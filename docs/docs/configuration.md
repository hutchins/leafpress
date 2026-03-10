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
```

## Field reference

### Top-level fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `company_name` | string | — | Company or organization name (required) |
| `project_name` | string | — | Project or document title (required) |
| `logo_path` | string | `null` | Path to logo (PNG/SVG/JPEG) or `https://` URL |
| `subtitle` | string | `null` | Subtitle shown on cover page |
| `author` | string | `null` | Author name |
| `author_email` | string | `null` | Author email |
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
| `LEAFPRESS_COPYRIGHT_TEXT` | `copyright_text` |
| `LEAFPRESS_PRIMARY_COLOR` | `primary_color` |
| `LEAFPRESS_ACCENT_COLOR` | `accent_color` |
| `LEAFPRESS_FOOTER_CUSTOM_TEXT` | `footer.custom_text` |
| `LEAFPRESS_FOOTER_REPO_URL` | `footer.repo_url` |
| `LEAFPRESS_FOOTER_INCLUDE_TAG` | `footer.include_tag` (`true`/`false`) |
| `LEAFPRESS_FOOTER_INCLUDE_DATE` | `footer.include_date` |
| `LEAFPRESS_FOOTER_INCLUDE_COMMIT` | `footer.include_commit` |
| `LEAFPRESS_FOOTER_INCLUDE_BRANCH` | `footer.include_branch` |

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
