# Zensical Projects

!!! warning "Experimental"
    [Zensical](https://zensical.org) is the successor to Material for MkDocs from the same team. It is pre-1.0; the stable 0.1.0 release line is scheduled for November 5, 2026. leafpress's support for `zensical.toml` is experimental and may change as the Zensical configuration format settles.

leafpress converts Zensical projects the same way it converts MkDocs projects: same commands, same output formats, same branding.

## Which config is used

Zensical can build from either an existing `mkdocs.yml` or its own `zensical.toml`. leafpress looks for, in order:

1. `mkdocs.yml`
2. `mkdocs.yaml`
3. `zensical.toml`

So a project that still has an `mkdocs.yml` converts exactly as before. If both files exist, leafpress uses `mkdocs.yml` and tells you so. To use the Zensical config instead, pass it explicitly:

```bash
leafpress convert . --mkdocs-config zensical.toml
```

Project auto-detection, `leafpress info`, and monorepo `projects:` entries recognize `zensical.toml` the same way.

## Supported settings

Only the settings leafpress needs are read, all from the `[project]` table:

| Setting | Notes |
|---------|-------|
| `site_name` | Document title (unless branding overrides it) |
| `docs_dir` | Relative to `zensical.toml`, defaults to `docs`, and must stay inside the project |
| `nav` | Same structure as in `mkdocs.yml`. Entries that are external links (`https://…`) are skipped, since there's no page to render |
| `markdown_extensions` | See below |
| `theme`, `extra_css` | Read for `leafpress info`; they don't affect output styling |

Everything else (`site_url`, `theme.features`, `extra`, …) is ignored.

### Markdown extensions

In TOML, each extension is its own table, and dotted names nest:

```toml
[project.markdown_extensions.admonition]

[project.markdown_extensions.toc]
permalink = true

[project.markdown_extensions.pymdownx.superfences]
custom_fences = [
  { name = "mermaid", class = "mermaid", format = "pymdownx.superfences.fence_code_format" },
]
```

leafpress turns these back into the extension names Python-Markdown expects (`admonition`, `toc`, `pymdownx.superfences`), with their options:

- An extension set to `false` is treated as disabled.
- Options that name a Python function as a string (`emoji_index`, `emoji_generator`, `slugify`, and custom fences' `format`) are dropped. `mkdocs.yml` `!!python/name:` tags get the same treatment. Mermaid diagrams are handled by leafpress itself (see [Markdown Extensions → Mermaid diagrams](extensions.md#mermaid-diagrams)).
- The same [file-reading restrictions](extensions.md#file-reading-extensions) apply as for `mkdocs.yml`.

### TOML 1.1

Some real-world `zensical.toml` files use TOML 1.1 syntax, such as line breaks inside `{ … }` inline tables. Zensical accepts this, so leafpress parses with [`tomli`](https://github.com/hukkin/tomli), which supports TOML 1.1, rather than Python's built-in `tomllib`.

## Known gaps

- **Unknown extension namespaces.** Extensions from packages other than `pymdownx`, `markdown`, `material`, and `zensical` are recognized when they're installed. If one isn't installed, its dotted name may be misread; it would fail to load anyway, with the usual "Skipping unavailable extension" warning.
- **Zensical-only Markdown extensions.** Extensions under `zensical.extensions.*` load only if the `zensical` package is installed alongside leafpress.
- **Zensical plugins and theme features** have no effect on leafpress output.
