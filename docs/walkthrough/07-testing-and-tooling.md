[Index](README.md) · ← Previous: [Python version comparisons](06-python-version-comparisons.md) · Next → [Index](README.md)

---

# Testing & tooling

## Running things

```bash
cd trade-pipeline
uv sync                        # install/update the environment
uv run pytest tests/ -q        # run the whole suite
uv run ruff check .            # lint (add --fix to auto-fix)
uv run pip-audit               # dependency vulnerability scan
```

As of the last update to this page: **53 tests passing**, ruff clean, no known vulnerabilities, zero
deprecation warnings (enforced — see below).

## Test layout

`tests/` mirrors `src/trade_pipeline/` exactly:

```
tests/
  common/       ← tests src/trade_pipeline/common/     (models, config, db_models, version demo)
  producer/     ← tests src/trade_pipeline/producer/
  consumer/     ← tests src/trade_pipeline/consumer/    (dedup logic + Postgres sink)
  api/          ← tests src/trade_pipeline/api/         (JWT, auth routes, trades route)
  enrichment/   ← tests src/trade_pipeline/enrichment/  (circuit breaker, hand-rolled, Temporal)
```

## Key config

**File**: [`trade-pipeline/pyproject.toml`](../../trade-pipeline/pyproject.toml)

- `[tool.pytest.ini_options]` — `asyncio_mode = "auto"` (async test functions don't need a decorator),
  and critically:
  ```toml
  filterwarnings = ["error::DeprecationWarning", "error::PendingDeprecationWarning"]
  ```
  This turns any deprecated API usage — ours or a dependency's — into a hard test failure instead of a
  silent warning. It's what caught `slowapi`'s internals calling a Python API slated for removal in
  3.16, which is why this project has a hand-rolled `RateLimitMiddleware` instead
  ([page 4](04-api-and-auth.md), [DECISIONS.md](../DECISIONS.md)).
- `[tool.ruff.lint]` — explicit `select = ["E", "F", "I", "UP", "B", "C4", "SIM", "RUF"]` rather than
  relying on ruff's defaults, plus a per-file exception for
  [`version_compat_demo.py`](../../trade-pipeline/src/trade_pipeline/common/version_compat_demo.py)
  (which deliberately keeps old-style syntax `UP` rules would otherwise "fix" away).

## Fakes over mocks

Real external systems (Kafka, Redis, Postgres) are never required for the unit test suite:

- **Redis** → hand-rolled `FakeRedis` (dedup tests) or `fakeredis.FakeRedis` (API tests) —
  see [`tests/consumer/test_dedup_consumer.py`](../../trade-pipeline/tests/consumer/test_dedup_consumer.py)
  and [`tests/api/conftest.py`](../../trade-pipeline/tests/api/conftest.py).
- **Postgres** → SQLite in-memory, sync (`tests/consumer/test_postgres_sink.py`) or async via
  `aiosqlite` with `StaticPool` (`tests/api/conftest.py` — `StaticPool` is needed so multiple sessions
  share the same in-memory DB, since default pooling gives each connection its own independent one).
- **Kafka** → not faked at all for unit tests; `run_producer`/`run_consumer`'s real-broker code paths
  are deferred to a not-yet-built end-to-end Docker Compose smoke test
  (see [tasks/backlog/T-9-pytest-suite.md](../tasks/backlog/T-9-pytest-suite.md)).
- **Temporal** — the one real exception: workflow tests run against an actual (local, time-skipping)
  Temporal test server, confirmed reachable in this environment — see
  [page 5](05-enrichment.md).

## FastAPI test client

[`tests/api/conftest.py`](../../trade-pipeline/tests/api/conftest.py) uses
`httpx.AsyncClient(transport=httpx.ASGITransport(app=app))` — the current FastAPI-recommended pattern
for genuine async tests, confirmed via research to supersede `starlette.testclient.TestClient` for
this purpose. Note: `ASGITransport` does not fire app lifespan events, which is why
`create_app()` builds all its resources (engine, Redis client) eagerly rather than in a
startup/shutdown hook.

---
[Index](README.md) · ← Previous: [Python version comparisons](06-python-version-comparisons.md) · Next → [Index](README.md)
