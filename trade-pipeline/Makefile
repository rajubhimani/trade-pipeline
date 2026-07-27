.PHONY: install lint test audit check services-up services-down up down logs ps restart demo db-upgrade db-revision

install:
	uv sync

lint:
	uv run ruff check .

# Apply pending Alembic migrations against POSTGRES_DSN (default: localhost,
# see common/config.py) — same path scripts/migrate.py runs in Docker.
db-upgrade:
	uv run alembic upgrade head

# Autogenerate a new revision from db_models.py changes. Always read the
# generated file before committing — autogenerate misses renames and some
# type changes.
db-revision:
	uv run alembic revision --autogenerate -m "$(m)"

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

# Whole system — infra (kafka/redis/postgres) plus the app's own producer,
# consumer, api, and dagster services, all built from ./Dockerfile.
# --build picks up local source changes; compose brings up dependencies
# (keys-init, migrate) in order via each service's `depends_on` condition.
up:
	docker compose up -d --build

down:
	docker compose down -v

restart: down up

ps:
	docker compose ps

logs:
	docker compose logs -f

# Quick smoke check against a running `make up` stack: log in as the demo
# user, then use the token to fetch trades — proves producer -> kafka ->
# consumer -> postgres -> api are all actually wired up, not just "started".
demo:
	@TOKEN=$$(curl -s -X POST localhost:8000/auth/login \
		-H "Content-Type: application/json" \
		-d '{"username":"demo","password":"trade-pipeline-demo"}' \
		| python -c "import sys,json;print(json.load(sys.stdin)['access_token'])") && \
	curl -s "localhost:8000/trades?limit=5" -H "Authorization: Bearer $$TOKEN"
