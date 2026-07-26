.PHONY: install lint test audit check

install:
	uv sync

lint:
	uv run ruff check .

test:
	uv run pytest tests/ -q

audit:
	uv run pip-audit

check: lint test audit
