.PHONY: tests lint format typecheck setup-hooks

tests: lint typecheck
	uv run pytest tests/ -v

lint:
	uv run ruff check src/ tests/

format:
	uv run ruff check --fix src/ tests/
	uv run ruff format src/ tests/

typecheck:
	uv run ty check

setup-hooks:
	git config core.hooksPath .githooks
