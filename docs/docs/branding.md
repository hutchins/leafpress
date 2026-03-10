# Branding & Styling

leafpress supports full branding customization via `leafpress.yml` or environment variables.

## Logo

Set `logo_path` to a local image file or a remote URL:

```yaml
# Local file (relative to leafpress.yml)
logo_path: "./logo.png"

# Absolute path
logo_path: "/usr/local/share/branding/logo.png"

# Home directory path
logo_path: "~/assets/logo.svg"

# Remote URL
logo_path: "https://example.com/logo.png"
```

Supported formats: PNG, SVG, JPEG.

The logo appears on the cover page. It is scaled to fit within the header area.

## Colors

Two color values control the branding palette:

```yaml
primary_color: "#1a73e8"    # Used for headings, cover page accents, footer rule
accent_color: "#ffffff"      # Background/contrast color
```

Both must be 6-digit hex values (e.g. `#1a73e8`). The `#` prefix is required. Values are normalized to lowercase.

## Cover page metadata

The cover page is assembled from these fields:

```yaml
company_name: "Acme Corp"       # shown as subtitle / organization
project_name: "Platform Docs"   # main document title
subtitle: "Internal Documentation"
author: "Engineering Team"
author_email: "team@example.com"
copyright_text: "Copyright © 2026 Acme Corp"
```

Git version info (tag, commit, branch) is also shown on the cover page if the project is a git repository. See [Git Integration](git-integration.md).

## Footer

The footer appears on every page (PDF) or at the end of the document (DOCX):

```yaml
footer:
  include_tag: true             # git tag (e.g. v1.2.0)
  include_date: true            # build date (YYYY-MM-DD)
  include_commit: true          # short commit hash
  include_branch: false         # branch name
  custom_text: "Confidential"   # static text, always shown if set
  repo_url: "https://github.com/org/repo"  # linked repository URL
```

Footer fields are rendered left-to-right, separated by `·`.

### Example footer output

```
v1.2.0 · 2026-03-08 · a1b2c3d · Confidential
```

## Environment variable overrides

All branding fields can be set or overridden via `LEAFPRESS_*` environment variables. See the full table in [Configuration](configuration.md#environment-variables).

```bash
export LEAFPRESS_PRIMARY_COLOR="#e53935"
export LEAFPRESS_COMPANY_NAME="Acme Corp"
```
