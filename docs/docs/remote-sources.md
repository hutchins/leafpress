# Remote Sources

leafpress can convert MkDocs sites directly from remote git repositories — no local clone needed.

## Usage

Pass a git URL as the `SOURCE` argument:

```bash
# Clone and convert the default branch
leafpress convert https://github.com/org/repo

# Convert a specific branch
leafpress convert https://github.com/org/repo -b main

# Convert a specific branch to DOCX
leafpress convert https://github.com/org/repo -b release/2.0 -f docx
```

## Supported URL formats

Any URL that `git clone` accepts:

```bash
# HTTPS
leafpress convert https://github.com/org/repo

# SSH
leafpress convert git@github.com:org/repo.git
```

## How it works

1. leafpress performs a **shallow clone** (`--depth 1`) of the repository to a temporary directory
2. The conversion runs against the cloned project
3. The temporary directory is cleaned up automatically when done

## Branch selection

Use `--branch` / `-b` to specify a branch, tag, or commit ref:

```bash
leafpress convert https://github.com/org/repo -b develop
leafpress convert https://github.com/org/repo -b v2.1.0
```

If not specified, git clones the remote's default branch.

## Authentication

For private repositories, ensure your git credentials are configured:

```bash
# SSH key (recommended)
git clone git@github.com:org/private-repo.git  # verify access first

# HTTPS with credential helper
git config --global credential.helper store
```

leafpress uses the system `git` command, so any configured authentication method (SSH keys, credential helpers, GitHub CLI) works automatically.

## `.env` and branding config

When converting a remote source, leafpress looks for `leafpress.yml` inside the cloned repository. A `.env` file in a cloned repository is **not** loaded, since it could set variables that change how git or other tools run on your machine. Provide branding via `--config` pointing to a local file, or via `LEAFPRESS_*` environment variables:

```bash
# Use a local branding config with a remote source
leafpress convert https://github.com/org/repo -b main -c ./my-branding.yml

# Use env vars (no local config needed)
LEAFPRESS_COMPANY_NAME="Acme" LEAFPRESS_PROJECT_NAME="Docs" \
  leafpress convert https://github.com/org/repo
```

## Converting untrusted repositories

A repository you convert controls its `mkdocs.yml`, `leafpress.yml`, and Markdown, so leafpress treats that content as untrusted and confines what it can reach. This applies to every source, not only remote ones. For example, a local CI checkout of a contributor's branch gets the same protections.

- **Pages** must live inside `docs_dir`. `docs_dir` must be inside the project directory. `nav` entries that are absolute or use `..` are dropped. Pages that are symlinks pointing outside `docs_dir` are skipped with a warning.
- **Images and other embedded files** must resolve inside the project directory (or the folder you ran `convert` on), after following symlinks, and must be real image files. Anything else, such as `<img src="../.env">`, is never embedded. This applies to Markdown images, raw HTML `<img>`, and `file://` URIs. References outside the project are blanked and listed in the "missing assets" warning. This applies to PDF, DOCX, and ODT output.
- **PDF resources** are fetched through a restricted fetcher (see [PDF Output](pdf.md#external-resources)). It blocks local files outside the project and requests to private or internal network addresses.
- **`pymdownx.snippets` and `pymdownx.b64`** are confined to the project directory. Remote snippet downloads (`url_download`) are disabled. See [Markdown Extensions](extensions.md#how-extensions-are-loaded).
- **A cloned repository's own `leafpress.yml` is untrusted.** Its `logo_path` must point inside the repository and be a real image. Its `mermaid.server` must be a public host. An explicit `-c` config and your `LEAFPRESS_*` environment variables are trusted, so a self-hosted internal mermaid server (`LEAFPRESS_MERMAID_SERVER`) keeps working.
- **Downloads never forward credentials to another origin.** When a redirect changes host, scheme, or port, `Authorization`, `Cookie`, and `Proxy-Authorization` headers are dropped. This covers, for example, the Lucidchart token following a redirect to a storage bucket.
- **`.env`** is not loaded from cloned repositories. For local projects, only `LEAFPRESS_*` keys are read from it.
- **Raw HTML is sanitized.** Scripts, event handlers (`onerror=`), `javascript:` links, iframes, forms, and resource-loading inline CSS are removed from page HTML. The normal MkDocs/Material markup is kept: admonitions, tabs, details, tables, task lists, footnotes, and highlighted code. This matters most for HTML and EPUB output, which would otherwise carry active content wherever they're published.
    - Sanitizing is automatic for git URL sources and monorepo `url:` projects, and a cloned repository's own `leafpress.yml` can't turn it off.
    - For local sources you don't fully trust, such as a CI checkout of a pull request, enable it with `--sanitize-html`, `LEAFPRESS_SANITIZE_HTML=true`, or `sanitize_html: true`.
- **Monorepo `projects[].path`** entries in a cloned repository's `leafpress.yml` must stay inside that repository.

Diagram fetching (`fetch-diagrams`) and the Mermaid renderer still make network requests. Only enable them for repositories you trust.

!!! note "Known limitation: DNS rebinding"
    The internal-host check resolves a hostname, then the HTTP client resolves it again to connect. A hostname built for DNS rebinding (public on the first lookup, internal on the second) can therefore slip through. The check stops ordinary SSRF payloads and misconfiguration, including IPv4 addresses wrapped in IPv6 such as NAT64 `64:ff9b::7f00:1`. If you convert untrusted repositories on hosts with sensitive internal endpoints, also restrict egress at the network level.

