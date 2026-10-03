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

!!! warning "SVG logo compatibility"
    SVG logos render in **PDF** (via Cairo/librsvg), **HTML** (native browser support), and **ODT** (embedded as SVG). **DOCX** only supports raster images, so an SVG logo is skipped there with a warning. For full format compatibility, use a PNG or JPEG logo.

## Colors

Two color values control the branding palette:

```yaml
primary_color: "#1a73e8"    # Used for headings, cover page accents, footer rule
accent_color: "#ffffff"      # Background/contrast color
```

Both must be 6-digit hex values (e.g. `#1a73e8`). The `#` prefix is optional. Values are normalized to lowercase.

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

The footer appears on every page in PDF and DOCX, and once at the end of HTML, EPUB, and ODT output:

```yaml
footer:
  include_tag: true             # git tag (e.g. v1.2.0)
  include_date: true            # date of the HEAD commit (YYYY-MM-DD)
  include_commit: true          # short commit hash
  include_branch: false         # branch name
  include_render_date: false    # append "Generated YYYY-MM-DD" to footer
  custom_text: "Confidential"   # static text, always shown if set
  repo_url: "https://github.com/org/repo"  # linked repository URL
```

In **PDF and DOCX** the footer is assembled in this order, joined by ` - `:

1. `custom_text`
2. `repo_url`
3. The version field: the enabled parts of tag, commit, commit date, and branch, joined by ` | `
4. `Generated YYYY-MM-DD` (if `include_render_date`)
5. The credit `Made with LeafPress · leafpress.dev`

### Example footer output

```
Confidential - https://github.com/org/repo - v1.2.0 | a1b2c3d | 2026-03-08 - Made with LeafPress · leafpress.dev
```

With `include_render_date: true`:

```
Confidential - https://github.com/org/repo - v1.2.0 | a1b2c3d | 2026-03-08 - Generated 2026-03-11 - Made with LeafPress · leafpress.dev
```

**HTML, EPUB, and ODT** use a simpler footer: `custom_text`, then the full [version string](git-integration.md#version-string), then the generation date, then `Made with LeafPress`. In these formats the `include_tag`, `include_commit`, `include_date`, `include_branch`, and `repo_url` settings currently have no effect.

The render date can also be toggled via the CLI:

```bash
leafpress convert . --footer-date      # enable generation date
leafpress convert . --no-footer-date   # disable generation date
```

## Environment variable overrides

Most branding fields (names, logo, colors, footer, watermark) can be set or overridden via `LEAFPRESS_*` environment variables; `pdf` and `docx` options are YAML-only. See the full table in [Configuration](configuration.md#environment-variables).

```bash
export LEAFPRESS_PRIMARY_COLOR="#e53935"
export LEAFPRESS_COMPANY_NAME="Acme Corp"
```
