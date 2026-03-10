# CI / CD Pipelines

leafpress is designed to run in any CI/CD system. Branding can be configured entirely via environment variables — no `leafpress.yml` file required.

## Using the GitHub Action

The easiest way to use leafpress in GitHub Actions is with the official composite action:

```yaml
jobs:
  docs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: hutchins/leafpress@main
        with:
          format: pdf
          output: dist
        env:
          LEAFPRESS_COMPANY_NAME: ${{ vars.COMPANY_NAME }}
          LEAFPRESS_PROJECT_NAME: My Docs

      - uses: actions/upload-artifact@v4
        with:
          name: documentation
          path: dist/
```

The action handles Python setup and WeasyPrint system dependencies automatically.

**Inputs:**

| Input | Default | Description |
|-------|---------|-------------|
| `source` | `.` | Path to MkDocs project directory |
| `output` | `dist` | Output directory |
| `format` | `pdf` | `pdf`, `docx`, `html`, `odt`, `epub`, `both` (pdf+docx), or `all` |
| `config` | _(auto-detect)_ | Path to `leafpress.yml` |
| `cover_page` | `true` | Include cover page |
| `toc` | `true` | Include table of contents |
| `local_time` | `false` | Use local timezone for dates instead of UTC |
| `python_version` | `3.13` | Python version to install |

**Outputs:**

| Output | Description |
|--------|-------------|
| `files` | Newline-separated list of generated file paths |

---

## Manual setup — quick start

```yaml
jobs:
  docs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install WeasyPrint system dependencies
        run: |
          sudo apt-get update
          sudo apt-get install -y libpango-1.0-0 libharfbuzz0b libpangoft2-1.0-0 libfontconfig1

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.13"

      - name: Install leafpress
        run: pip install leafpress

      - name: Convert docs to PDF
        env:
          LEAFPRESS_COMPANY_NAME: ${{ vars.COMPANY_NAME }}
          LEAFPRESS_PROJECT_NAME: My Project
          LEAFPRESS_PRIMARY_COLOR: "#1a73e8"
        run: leafpress convert . -f pdf -o dist/

      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: documentation
          path: dist/*.pdf
```

## Environment variable configuration

Set `LEAFPRESS_*` variables to configure branding without a YAML file. If both `LEAFPRESS_COMPANY_NAME` and `LEAFPRESS_PROJECT_NAME` are set and no `leafpress.yml` exists in the project, leafpress builds the config from env vars only.

| Environment variable | Config field | Notes |
|----------------------|-------------|-------|
| `LEAFPRESS_COMPANY_NAME` | `company_name` | Required for env-only mode |
| `LEAFPRESS_PROJECT_NAME` | `project_name` | Required for env-only mode |
| `LEAFPRESS_LOGO_PATH` | `logo_path` | Local path or `https://` URL |
| `LEAFPRESS_SUBTITLE` | `subtitle` | |
| `LEAFPRESS_AUTHOR` | `author` | |
| `LEAFPRESS_AUTHOR_EMAIL` | `author_email` | |
| `LEAFPRESS_COPYRIGHT_TEXT` | `copyright_text` | |
| `LEAFPRESS_PRIMARY_COLOR` | `primary_color` | 6-digit hex, e.g. `#1a73e8` |
| `LEAFPRESS_ACCENT_COLOR` | `accent_color` | |
| `LEAFPRESS_FOOTER_CUSTOM_TEXT` | `footer.custom_text` | |
| `LEAFPRESS_FOOTER_REPO_URL` | `footer.repo_url` | |
| `LEAFPRESS_FOOTER_INCLUDE_TAG` | `footer.include_tag` | `true` or `false` |
| `LEAFPRESS_FOOTER_INCLUDE_DATE` | `footer.include_date` | |
| `LEAFPRESS_FOOTER_INCLUDE_COMMIT` | `footer.include_commit` | |
| `LEAFPRESS_FOOTER_INCLUDE_BRANCH` | `footer.include_branch` | |
| `LEAFPRESS_LOCAL_TIME` | _(CLI flag)_ | `true` or `false` — use local timezone for dates |
| `LEAFPRESS_LUCIDCHART_TOKEN` | `diagrams.lucidchart_token` | API token for Lucidchart diagram exports |

**Priority:** shell env > `.env` file > `leafpress.yml` > built-in defaults

Env vars override YAML values when both are present, so you can keep a `leafpress.yml` for local use and let CI inject secrets (like logo URLs or company names) without modifying the file.

## Using GitHub Actions variables and secrets

Store sensitive or org-wide values as [repository variables](https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/store-information-in-variables) (`vars.*`) or [secrets](https://docs.github.com/en/actions/security-for-github-actions/security-guides/using-secrets-in-github-actions) (`secrets.*`):

```yaml
env:
  LEAFPRESS_COMPANY_NAME: ${{ vars.COMPANY_NAME }}
  LEAFPRESS_LOGO_PATH: ${{ vars.LOGO_URL }}
  LEAFPRESS_FOOTER_REPO_URL: ${{ github.server_url }}/${{ github.repository }}
```

## `.env` file support

leafpress automatically loads a `.env` file from the project root before applying config. This is useful for local development; in CI, use shell env vars directly (they take priority over `.env`).

```bash
# .env (do not commit secrets)
LEAFPRESS_COMPANY_NAME=Acme Corp
LEAFPRESS_PROJECT_NAME=Platform Docs
```

!!! warning
    Do not commit `.env` files containing secrets. Add `.env` to `.gitignore`.

## Overriding YAML config in CI

If you have a `leafpress.yml` in the repo, env vars will override its fields. This lets you keep defaults in YAML and inject environment-specific values in CI:

```yaml
# leafpress.yml (committed)
company_name: "Acme Corp"
project_name: "Platform Docs"
primary_color: "#1a73e8"
footer:
  include_tag: true
```

```yaml
# GitHub Actions step
env:
  LEAFPRESS_FOOTER_CUSTOM_TEXT: "Build ${{ github.run_number }}"
  LEAFPRESS_FOOTER_REPO_URL: "${{ github.server_url }}/${{ github.repository }}"
```

## Full workflow example (all formats)

```yaml
name: Generate Documentation

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  docs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # full history for git version info

      - name: Install WeasyPrint system dependencies
        run: |
          sudo apt-get update
          sudo apt-get install -y \
            libpango-1.0-0 \
            libharfbuzz0b \
            libpangoft2-1.0-0 \
            libfontconfig1

      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"

      - name: Install leafpress
        run: pip install leafpress

      - name: Convert docs
        env:
          LEAFPRESS_COMPANY_NAME: ${{ vars.COMPANY_NAME }}
          LEAFPRESS_PROJECT_NAME: ${{ github.event.repository.name }}
          LEAFPRESS_FOOTER_REPO_URL: ${{ github.server_url }}/${{ github.repository }}
          LEAFPRESS_FOOTER_CUSTOM_TEXT: "Build ${{ github.run_number }}"
        run: leafpress convert . -f all -o dist/

      - name: Upload documentation
        uses: actions/upload-artifact@v4
        with:
          name: documentation
          path: dist/
```

!!! tip "Full git history"
    Use `fetch-depth: 0` in the checkout step so leafpress can read git tags and commit history for version info in the footer.

---

## GitLab CI

leafpress works on GitLab CI (and any other CI system) with the same `LEAFPRESS_*` environment variables.

### Quick start

```yaml
# .gitlab-ci.yml
generate-docs:
  image: python:3.13-slim
  variables:
    LEAFPRESS_COMPANY_NAME: "Acme Corp"
    LEAFPRESS_PROJECT_NAME: "Platform Docs"
    LEAFPRESS_PRIMARY_COLOR: "#1a73e8"
  before_script:
    - apt-get update && apt-get install -y libpango-1.0-0 libharfbuzz0b libpangoft2-1.0-0 libfontconfig1
    - pip install leafpress
  script:
    - leafpress convert . -f all -o dist/
  artifacts:
    paths:
      - dist/
```

### Using CI/CD variables

Store branding values in **Settings > CI/CD > Variables** and reference them in your pipeline:

```yaml
generate-docs:
  image: python:3.13-slim
  variables:
    LEAFPRESS_COMPANY_NAME: $COMPANY_NAME
    LEAFPRESS_PROJECT_NAME: $CI_PROJECT_NAME
    LEAFPRESS_FOOTER_REPO_URL: $CI_PROJECT_URL
    LEAFPRESS_FOOTER_CUSTOM_TEXT: "Build $CI_PIPELINE_IID"
    GIT_DEPTH: 0  # full history for git version info
  before_script:
    - apt-get update && apt-get install -y libpango-1.0-0 libharfbuzz0b libpangoft2-1.0-0 libfontconfig1
    - pip install leafpress
  script:
    - leafpress convert . -f all -o dist/
  artifacts:
    paths:
      - dist/
```

!!! tip "Full git history"
    Set `GIT_DEPTH: 0` in variables so leafpress can read git tags and commit history for version info in the footer.

---

## Fetching diagrams in CI

If your project uses external diagrams (URLs or Lucidchart), add `--fetch-diagrams` to your convert step:

```yaml
      - name: Convert docs (with diagrams)
        env:
          LEAFPRESS_LUCIDCHART_TOKEN: ${{ secrets.LUCIDCHART_TOKEN }}
        run: leafpress convert . -c leafpress.yml -f pdf -o dist/ --fetch-diagrams
```

Or run the fetch step separately for more control:

```yaml
      - name: Fetch diagrams
        env:
          LEAFPRESS_LUCIDCHART_TOKEN: ${{ secrets.LUCIDCHART_TOKEN }}
        run: leafpress fetch-diagrams -c leafpress.yml --refresh

      - name: Convert docs
        run: leafpress convert . -c leafpress.yml -f pdf -o dist/
```

!!! tip "Store tokens as secrets"
    Always store `LEAFPRESS_LUCIDCHART_TOKEN` as a repository secret, not a variable. It grants read access to your Lucidchart documents.

See [Diagrams](diagrams.md) for full configuration details.

---

## Other CI systems

leafpress runs anywhere Python is available. The general steps are:

1. Install system dependencies (Pango and friends — see [Installation](installation.md#weasyprint-system-dependencies))
2. Install leafpress: `pip install leafpress`
3. Set `LEAFPRESS_*` environment variables for branding
4. Run `leafpress convert . -f <format> -o dist/`

No GitHub- or GitLab-specific features are required. The `LEAFPRESS_*` env vars and `.env` file support work identically on every platform.
