# Git Integration

LeafPress automatically reads git metadata from the project directory and embeds it in the output document.

## What is extracted

| Field | Description | Example |
|-------|-------------|---------|
| Tag | Most recent annotated git tag | `v1.2.0` |
| Branch | Current branch name | `main` |
| Commit hash | Short (7-char) commit SHA | `a1b2c3d` |
| Commit date | Date of the HEAD commit | `2026-03-08` |
| Dirty flag | Whether working tree has uncommitted changes | `true`/`false` |

## Version string

LeafPress formats git info into a human-readable version string:

- **Tagged release:** `v1.2.0`
- **Untagged commit:** `main@a1b2c3d`
- **Dirty working tree:** appends `-dirty`

This string appears on the cover page and in the footer (if `include_tag` or `include_commit` is enabled).

## Footer fields

Control which git fields appear in the footer:

```yaml
footer:
  include_tag: true       # show git tag (e.g. v1.2.0)
  include_date: true      # show commit date
  include_commit: true    # show short commit hash
  include_branch: false   # show branch name
```

## Remote sources

When converting from a remote git URL, LeafPress clones the repository first, then reads git info from the clone. See [Remote Sources](remote-sources.md).

## Full git history in CI

For accurate tag detection in CI, ensure you check out the full git history:

```yaml
- uses: actions/checkout@v4
  with:
    fetch-depth: 0    # required for git tags
```

Without `fetch-depth: 0`, shallow clones may not have tags, and LeafPress will fall back to the commit hash.

## No git repository

If the project directory is not a git repository, git info is silently omitted from the output. No error is raised.
