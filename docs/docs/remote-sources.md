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

When converting a remote source, leafpress looks for `leafpress.yml` and `.env` inside the cloned repository. You can also provide branding via `--config` pointing to a local file, or via `LEAFPRESS_*` environment variables:

```bash
# Use a local branding config with a remote source
leafpress convert https://github.com/org/repo -b main -c ./my-branding.yml

# Use env vars (no local config needed)
LEAFPRESS_COMPANY_NAME="Acme" LEAFPRESS_PROJECT_NAME="Docs" \
  leafpress convert https://github.com/org/repo
```
