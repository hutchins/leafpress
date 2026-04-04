.PHONY: tests lint format typecheck setup-hooks

tests: lint typecheck
	uv run pytest tests/ -v

lint:
	uv run ruff check src/

format:
	uv run ruff check --fix src/
	uv run ruff format src/

typecheck:
	-uv run ty check

setup-hooks:
	git config core.hooksPath .githooks
