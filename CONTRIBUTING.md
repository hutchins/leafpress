# Contributing to LeafPress

Thanks for your interest in contributing!

## Development setup

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/hutchins/leafpress.git
cd leafpress
uv sync --group dev
```

### WeasyPrint system dependencies (Linux/macOS)

PDF rendering requires Pango. On Ubuntu/Debian:

```bash
sudo apt-get install -y libpango-1.0-0 libharfbuzz0b libpangoft2-1.0-0 libfontconfig1
```

On macOS:

```bash
brew install pango
```

## Running tests

```bash
uv run pytest tests/ -q
```

## Linting

```bash
uv run ruff check src/
uv run ruff format --check src/
```

## Submitting a pull request

1. Fork the repo and create a branch from `main`
2. Make your changes with tests
3. Ensure `pytest` and `ruff` pass
4. Open a PR — the PR template will guide you

## Reporting issues

Use the [GitHub issue tracker](https://github.com/hutchins/leafpress/issues). Bug reports and feature requests both have structured templates to fill in.
