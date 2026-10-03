# Contributing to LeafPress

Thanks for your interest in contributing!

## Development setup

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/hutchins/leafpress.git
cd leafpress
uv sync --group dev
make setup-hooks   # pre-commit: ruff check, ruff format --check, ty
```

### WeasyPrint system dependencies (Linux/macOS)

PDF rendering requires Pango. On Ubuntu/Debian:

```bash
sudo apt-get install -y libpango-1.0-0 libharfbuzz0b libpangoft2-1.0-0 libfontconfig1
```

On macOS:

```bash
brew install pango
# If WeasyPrint can't find the libraries (e.g. "cannot load library 'libgobject-2.0-0'"):
export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib
```

## Running checks

```bash
make tests                 # lint + type check + full test suite
uv run pytest tests/ -q    # tests only
uv run ruff check .        # lint
uv run ruff format --check .
uvx ty check               # type check (CI pins the ty version)
```

CI also runs `pip-audit` against the lockfile. After changing dependencies, check locally with:

```bash
uv export --all-extras --all-groups --no-hashes --no-emit-project \
  --format requirements-txt > /tmp/req.txt
uvx pip-audit -r /tmp/req.txt --no-deps --disable-pip
```

## Test layout

Tests live in `tests/`, one file per module (`test_<module>.py`), plus a few cross-cutting suites:

| File | Covers |
|------|--------|
| `test_pipeline.py`, `test_pipeline_monorepo.py` | End-to-end `convert()` for each format and monorepo mode |
| `test_untrusted_content.py`, `test_download_hardening.py`, `test_sanitize.py`, `test_security.py` | Security boundaries: file confinement, URL fetching, downloads, HTML sanitizing, YAML safety. **Add a regression test here for any change that touches what content can read, fetch, or execute** |
| `test_images_and_mermaid_config.py` | Image embedding per format, mermaid configuration, temp-dir cleanup |
| `test_cibutler_integration.py` | A real Material for MkDocs site (see below) |
| `test_docker.py` | Builds and runs the Docker image (marked `docker`) |
| `test_docs_site.py` | Sanity checks on this repo's own `docs/` site |

### Fixtures and helpers

- `tests/conftest.py`:
    - `sample_mkdocs_dir` / `sample_mkdocs_config`: the small project in `tests/fixtures/sample_mkdocs_project/`
    - `sample_branding_config`: `tests/fixtures/sample_config.yml`
    - `tmp_output`: an output directory under `tmp_path`
    - `sample_docx` / `comprehensive_docx`: generated Word files for importer tests
- `tests/helpers.py`: `make_png()` builds a minimal valid PNG for embedding tests.
- Mock HTTP by patching `leafpress.downloads.requests.get`. All downloads go through `leafpress.downloads.download()`, which streams, so fake responses need `iter_content()`, `is_redirect`, `headers`, and `raise_for_status()`. See `_Resp` in `test_download_hardening.py`.
- Prefer building small projects in `tmp_path` over adding fixture files.

### Markers and optional suites

- `pytest -m docker` runs the Docker image tests, which require a running Docker daemon. Use `-m "not docker"` to skip them.
- The CIButler integration tests run against a checkout of the CIButler docs. Point `LEAFPRESS_CIBUTLER_DOCS` at the checkout's directory that contains `mkdocs.yml`. Without it, the tests are skipped with a message saying so.

## Adding an output format (renderer)

1. **Create the package.** Create `src/leafpress/<format>/renderer.py` with a class following the `BaseRenderer` protocol in `base_renderer.py`: `__init__(branding, git_info, mkdocs_cfg)` and `render(html_pages, output_path, cover_page, include_toc, local_time)`.
2. **Confine local file reads.** If the renderer reads local files referenced by page HTML (images, attachments), also accept `asset_policy: AssetPolicy | None = None`.
    - Default it to `build_asset_policy(mkdocs_cfg, branding)`.
    - Check every path with `asset_policy.allows(path)` before reading it.
    - Page content may come from an untrusted repository.
    - `rewrite_local_images()` in `base_renderer.py` handles the common "embed `<img src="file://...">`" case.
3. **Wire it into the pipeline.** In `pipeline.py`, pass `asset_policy=asset_policy`, and add the format to `OutputFormat` in `cli.py`.
4. **Add tests and docs.** Add `tests/test_<format>_renderer.py` and a `docs/docs/<format>.md` page.

## Adding an import format (importer)

1. **Create the converter.** Create `src/leafpress/importer/converter_<ext>.py` returning an `ImportResult` (see `importer/base.py`).
    - Reuse `resolve_output_path`, `postprocess_markdown`, and `rows_to_pipe_table`.
    - Save images through `ImageHandler`.
2. **Confine file reads.** Only read files inside the input document's directory; check with `asset_policy.is_within()`. See `_resolve_image_path` in `converter_tex.py`.
3. **Register the extension.** Add it to `_SUPPORTED_IMPORT_EXTENSIONS` and the dispatch in `cli.py`.
4. **Add tests and docs.** Add `tests/test_import_<ext>.py` and a section in `docs/docs/import.md`.

## Documentation and changelog

Behavior changes need matching updates in `docs/docs/`, and an entry in `docs/docs/changelog.md` under the upcoming version. Check the site builds cleanly:

```bash
cd docs
uvx --with mkdocs-material --with mkdocs-git-revision-date-plugin --with termynal \
  mkdocs build --strict
```

## Submitting a pull request

1. Fork the repo and create a branch from `main`
2. Make your changes with tests
3. Ensure `ruff`, `ty`, and `pytest` pass
4. Open a PR; the PR template will guide you

## Reporting issues

Use the [GitHub issue tracker](https://github.com/hutchins/leafpress/issues). Bug reports and feature requests both have structured templates to fill in.

Please report security vulnerabilities privately as described in [SECURITY.md](SECURITY.md), not in public issues.
