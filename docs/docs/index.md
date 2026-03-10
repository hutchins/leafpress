---
template: home.html
hide:
  - navigation
  - toc
---

<div class="badges" markdown>

[![PyPI](https://img.shields.io/pypi/v/leafpress?color=2e7d32)](https://pypi.org/project/leafpress/)
[![License: MIT](https://img.shields.io/badge/License-MIT-2e7d32.svg)](https://github.com/hutchins/leafpress/blob/main/LICENSE)
[![CI](https://github.com/hutchins/leafpress/actions/workflows/ci.yml/badge.svg)](https://github.com/hutchins/leafpress/actions/workflows/ci.yml)

</div>

<div class="feature-grid" markdown>

<div class="feature-card" markdown>
<span class="feature-card__icon">:material-file-pdf-box:</span>
<p class="feature-card__title">Multiple Output Formats</p>
<p class="feature-card__desc">Generate PDF, DOCX, HTML, and ODT files from any MkDocs project with a single command.</p>
</div>

<div class="feature-card" markdown>
<span class="feature-card__icon">:material-palette-outline:</span>
<p class="feature-card__title">Custom Branding</p>
<p class="feature-card__desc">Cover pages, logos, colors, and footers — all configurable via leafpress.yml.</p>
</div>

<div class="feature-card" markdown>
<span class="feature-card__icon">:material-git:</span>
<p class="feature-card__title">Git-Aware</p>
<p class="feature-card__desc">Automatically embeds tag, branch, commit hash, and date into your documents.</p>
</div>

<div class="feature-card" markdown>
<span class="feature-card__icon">:material-console:</span>
<p class="feature-card__title">CLI & Desktop UI</p>
<p class="feature-card__desc">Use the command line for automation or the desktop app for a visual workflow.</p>
</div>

<div class="feature-card" markdown>
<span class="feature-card__icon">:material-github:</span>
<p class="feature-card__title">CI / GitHub Actions</p>
<p class="feature-card__desc">Run in pipelines with environment variables and the built-in GitHub Action.</p>
</div>

<div class="feature-card" markdown>
<span class="feature-card__icon">:material-cloud-download-outline:</span>
<p class="feature-card__title">Remote Sources</p>
<p class="feature-card__desc">Convert directly from git URLs — no need to clone repos manually.</p>
</div>

</div>

<div class="quick-start" markdown>

## Quick Start

```termynal
$ pip install leafpress
---> 100%
Successfully installed leafpress

$ leafpress init
Created leafpress.yml

$ leafpress convert . -f pdf -o dist/
Converting MkDocs site to PDF...
✓ dist/docs.pdf

$ leafpress convert . -f all -c leafpress.yml -o dist/
Converting MkDocs site to all formats...
✓ dist/docs.pdf
✓ dist/docs.docx
✓ dist/docs.html
✓ dist/docs.odt
```

</div>

## Next Steps

<div class="next-steps" markdown>

<a href="installation/">
  Installation
  <small>System requirements and setup</small>
</a>

<a href="configuration/">
  Configuration
  <small>Full leafpress.yml reference</small>
</a>

<a href="cli/">
  CLI Reference
  <small>All commands and flags</small>
</a>

<a href="ui/">
  Desktop UI
  <small>Menu bar app</small>
</a>

<a href="ci/">
  CI / GitHub Actions
  <small>Use in pipelines</small>
</a>

<a href="branding/">
  Branding & Styling
  <small>Logos, colors, and covers</small>
</a>

</div>
