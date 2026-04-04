# About

## What is LeafPress?

LeafPress converts [MkDocs](https://www.mkdocs.org/) documentation sites into professional, branded documents. It takes your existing Markdown content and produces PDF, Word (DOCX), HTML, ODT, EPUB, and consolidated Markdown files — complete with cover pages, tables of contents, version info, and your organization's branding.

## Why LeafPress?

Documentation teams often need to deliver polished documents alongside their web-based docs. Proposals, compliance reports, client deliverables, and internal handbooks all benefit from a formatted, downloadable document. LeafPress bridges this gap by turning MkDocs projects into print-ready output without leaving the tools you already use.

LeafPress also helps teams move their documentation into source control. Many organizations have years of knowledge locked in Word documents, PowerPoint decks, Excel spreadsheets, and LaTeX papers scattered across shared drives and email threads. The `leafpress import` command converts these files to Markdown — preserving headings, tables, images, math, and formatting — so teams can bring existing content into an MkDocs project and manage it alongside their code. Once in Markdown, documentation benefits from version history, pull request reviews, and automated publishing.

The consolidated Markdown export (`-f markdown`) goes the other direction — combining an entire MkDocs site into a single `.md` file. This is especially useful for feeding documentation to large language models as context, pasting into wikis or knowledge bases, or sharing a lightweight snapshot of your docs without requiring a browser or PDF viewer.

## Key Principles

- **Zero lock-in** — Your source stays as standard Markdown in MkDocs. LeafPress is a build tool, not a new authoring format.
- **Automation first** — Designed for CI/CD pipelines, GitHub Actions, and Docker. Generate documents on every push or release.
- **Batteries included** — Cover pages, TOC, git metadata, watermarks, and branding all work out of the box with minimal configuration.

## Author

LeafPress is built and maintained by **Shane Hutchins**, an enterprise architect and software engineer focused on developer tools and documentation workflows.

- GitHub: [github.com/hutchins](https://github.com/hutchins)

## License

LeafPress is released under the [MIT License](https://github.com/hutchins/leafpress/blob/main/LICENSE). You are free to use, modify, and distribute it in personal and commercial projects.

## Contributing

Contributions are welcome. If you'd like to report a bug, request a feature, or submit a pull request:

- [Open an issue](https://github.com/hutchins/leafpress/issues)
- [View the source](https://github.com/hutchins/leafpress)
