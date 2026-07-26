.PHONY: install lint test audit check services-up services-down

install:
	uv sync

lint:
	uv run ruff check .

# Tests need real Postgres + Redis reachable at localhost (docker-compose.yml
# services) — see tests/conftest.py. -n auto runs them in parallel via
# pytest-xdist, safe because each worker gets its own Postgres schema and
# Redis DB index.
test:
	uv run pytest tests/ -n auto -v

audit:
	uv run pip-audit

check: lint test audit

services-up:
	docker compose up -d postgres redis

services-down:
	docker compose down -v
