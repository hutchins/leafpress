.PHONY: tests lint format typecheck secrets setup-hooks

tests: lint typecheck
	uv run pytest tests/ -v

lint:
	uv run ruff check .

format:
	uv run ruff check --fix .
	uv run ruff format .

typecheck:
	uvx ty@0.0.84 check

secrets:
	gitleaks git . --redact --no-banner

setup-hooks:
	git config core.hooksPath .githooks
