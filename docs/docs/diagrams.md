# Diagrams

leafpress can fetch diagrams from external sources — URLs or Lucidchart — and save them locally before converting your MkDocs site. This keeps your documentation builds reproducible without committing large binary assets to version control.

!!! tip "Mermaid diagrams"
    If your diagrams are written as Mermaid code blocks in Markdown, you don't need the fetch workflow — LeafPress renders them automatically. See [Markdown Extensions → Mermaid diagrams](extensions.md#mermaid-diagrams) for details.

## Configuration

Add a `diagrams` section to your `leafpress.yml`:

```yaml
diagrams:
  cache_max_age: 3600     # seconds before re-downloading (0 = always refresh)
  sources:
    - url: https://example.com/diagrams/architecture.svg
      dest: docs/assets/diagrams/architecture.svg

    - url: https://example.com/diagrams/data-flow.png
      dest: docs/assets/diagrams/data-flow.png

    - lucidchart: abc123-document-id
      dest: docs/assets/diagrams/network.png
      page: 1
```

Each source needs a `dest` path (relative to your `leafpress.yml`) and either a `url` or `lucidchart` document ID.

### Source fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `url` | string | _(none)_ | HTTP/HTTPS URL to download |
| `lucidchart` | string | _(none)_ | Lucidchart document ID to export |
| `dest` | string | _(required)_ | Local path to save the file (relative to config) |
| `page` | integer | `1` | Page number to export (Lucidchart only) |

!!! tip "URL or Lucidchart"
    Each source should specify either `url` or `lucidchart`, not both. Sources with neither are skipped.

### Diagrams config fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `cache_max_age` | integer | `3600` | Seconds before a cached file is considered stale |
| `lucidchart_token` | string | _(none)_ | Lucidchart API token (prefer env var instead) |
| `sources` | list | `[]` | List of diagram sources to fetch |

## CLI usage

### Standalone command

```bash
# Fetch using auto-detected leafpress.yml in current directory
leafpress fetch-diagrams

# Specify a config file
leafpress fetch-diagrams --config path/to/leafpress.yml

# Force re-download, ignoring cache
leafpress fetch-diagrams --refresh

# Show detailed error output
leafpress fetch-diagrams --verbose
```

### Combined with convert

Use `--fetch-diagrams` on the `convert` command to fetch diagrams as a pre-step:

```bash
leafpress convert ./my-docs -c leafpress.yml --fetch-diagrams
```

This runs the fetch before converting, so your diagrams are always up to date.

## Using fetched diagrams in MkDocs

Once fetched, reference diagrams in your Markdown files like any other image:

```markdown
# Architecture

![System Architecture](assets/diagrams/architecture.svg)

# Data Flow

![Data Flow](assets/diagrams/data-flow.png)
```

The `dest` paths in your config should point into your MkDocs `docs/` directory so that MkDocs can find them during both `mkdocs serve` and `leafpress convert`.

!!! tip "Directory convention"
    A common pattern is to store fetched diagrams in `docs/assets/diagrams/` to keep them separate from hand-created images.

## Lucidchart setup

To export diagrams from Lucidchart, you need an API token.

### Getting a token

1. Go to [Lucidchart Account Settings](https://app.lucidchart.com/users/settings) and navigate to **API Tokens**
2. Generate a new token with read access to your documents
3. Copy the token value

### Configuring the token

Set it via environment variable (recommended):

```bash
export LEAFPRESS_LUCIDCHART_TOKEN="your-token-here"
```

Or in `leafpress.yml` (less secure — avoid committing tokens):

```yaml
diagrams:
  lucidchart_token: "your-token-here"
```

!!! warning "Keep tokens out of version control"
    Use the `LEAFPRESS_LUCIDCHART_TOKEN` environment variable or a `.env` file (added to `.gitignore`) instead of hardcoding tokens in config files.

### Document IDs

The document ID is the alphanumeric string in a Lucidchart URL:

```
https://lucid.app/lucidchart/abc123-document-id/edit
                               ^^^^^^^^^^^^^^^^^^^^
                               This is the document ID
```

Diagrams are exported as PNG images. Use the `page` field to select a specific page (defaults to page 1).

## Caching

Fetched diagrams are cached locally at their `dest` path. On subsequent runs:

- If the file exists and is **newer** than `cache_max_age` seconds, it is skipped
- If the file is **older** than `cache_max_age` or missing, it is re-downloaded
- Use `--refresh` to force re-download regardless of cache age

Set `cache_max_age: 0` to always re-download on every run.

### Mermaid diagram caching

Mermaid diagrams rendered via [mermaid.ink](https://mermaid.ink) are cached using content-addressed filenames — identical diagram source always maps to the same cache file. Cached images are validated on each build by checking for valid PNG headers; corrupted files (e.g. from a partial write or disk error) are automatically re-rendered.

## Example workflow

A typical workflow for a project with external diagrams:

**1. Configure sources in `leafpress.yml`:**

```yaml
company_name: "Acme Corp"
project_name: "Platform Docs"

diagrams:
  cache_max_age: 7200
  sources:
    - url: https://cdn.example.com/arch-v3.svg
      dest: docs/assets/diagrams/architecture.svg
    - lucidchart: a1b2c3-doc-id
      dest: docs/assets/diagrams/network-topology.png
      page: 2
```

**2. Fetch diagrams:**

```bash
export LEAFPRESS_LUCIDCHART_TOKEN="your-token"
leafpress fetch-diagrams -c leafpress.yml
```

**3. Reference in Markdown:**

```markdown
## Architecture Overview

![Architecture](assets/diagrams/architecture.svg)

## Network Topology

![Network](assets/diagrams/network-topology.png)
```

**4. Convert:**

```bash
leafpress convert ./my-docs -c leafpress.yml -f pdf
```

Or combine fetch and convert in one step:

```bash
leafpress convert ./my-docs -c leafpress.yml -f pdf --fetch-diagrams
```

## CI/CD integration

In a CI pipeline, fetch diagrams before converting:

```yaml
# GitHub Actions example
steps:
  - uses: actions/checkout@v4

  - name: Fetch diagrams and convert
    env:
      LEAFPRESS_LUCIDCHART_TOKEN: ${{ secrets.LUCIDCHART_TOKEN }}
    run: |
      leafpress convert . -c leafpress.yml -f pdf --fetch-diagrams
```
