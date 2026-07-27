# Feature: Real Postgres/Redis in tests, xdist parallelism

Status: shipped
Task: docs/tasks/completed/T-19-real-service-testing.md

## Problem / motivation

Explicit request: replace SQLite-in-memory and `fakeredis`/hand-rolled Redis fakes with the real
`postgres:18.4-alpine` and `redis:8.8-alpine` containers this project's own `docker-compose.yml`
already defines, and use `pytest-xdist` to keep the suite fast despite talking to real services. This
also directly unblocked Postgres partitioning (`docs/features/postgres-partitioning.md`): partitioning
requires a composite `(id, timestamp)` primary key, which SQLite cannot autoincrement at all — the
conflict disappears once there's no second dialect to keep the schema compatible with.

## Scope

In: `tests/conftest.py` — shared fixtures (`pg_engine`, `pg_async_engine`, `pg_async_session`,
`redis_client`) backing every DB/Redis-touching test in the suite. Per-xdist-worker isolation (own
Postgres schema via `search_path`, own Redis logical DB index) and per-test isolation (fresh
schema / flushed DB every test). CI (`.github/workflows/ci.yml`) updated to run real Postgres/Redis as
GitHub Actions `services:` containers, matrixed across Python 3.11–3.14 as before, with
`pytest tests/ -n auto -q`.

Out:
- Kafka as a CI service / in the automated test suite — producer/consumer code touching a real broker
  remains manually verified (see `docs/tasks/completed/T-17-docker-image-upgrades.md`). No first-party
  GitHub Actions Kafka service, and meaningfully more fragile to run ad hoc than Postgres/Redis.
- `testcontainers`-style ephemeral per-test containers — this project's docker-compose services are
  long-lived (started once via `docker compose up -d`), with isolation achieved at the schema/DB level
  instead of spinning up/tearing down containers per test run. Simpler, and fast enough at this
  project's test count.

## Design

- **Per-worker Postgres schema, not per-worker database**: `CREATE SCHEMA test_worker_N` + `search_path`
  scoping is cheap and fast compared to creating/dropping whole databases per worker, while still
  giving full table isolation between workers.
- **Per-worker Redis DB index (0–15)**: Redis's built-in logical database separation is exactly this
  use case — no extra infrastructure needed, just `Redis.from_url(url, db=worker_index)`.
- **Fresh schema per test, not per session**: `pg_engine` drops and recreates its worker's schema
  (tables + partitions) on every test, trading a small amount of per-test overhead for zero risk of
  cross-test state leakage or ordering dependence — acceptable at this project's test count and real
  Postgres's speed for small schemas.
- **`pg_async_engine` depends on `pg_engine`**: purely so schema setup (which currently only has a sync
  implementation, using `psycopg`) runs before any async test touches the database, without every async
  test needing to explicitly request the sync fixture too.
- **`FakeMessage` (Kafka message stand-in) is kept**: it isn't a service fake — there's no Kafka
  connection to be faithful to, it's a minimal double for a data-carrying object's `.value()` method,
  same category as constructing a plain dict/namedtuple for a test. Removing SQLite/fakeredis doesn't
  mean removing every test double, just the ones standing in for a real backing service.

## Python version notes

No version-gated syntax; targets the full 3.11–3.14 range (CI matrix confirms this against real
services now, not just against SQLite/fakeredis which could theoretically mask a Postgres/Redis-version
behavioral difference).

## Testing plan

This *is* the testing infrastructure — validated by every other test file in the suite now depending on
it. Specific checks performed while building it:
- Verified fixture isolation directly: a test inserting a row and a separate test asserting an empty
  state both pass reliably under `pytest -n 4`, including when pytest-xdist schedules them on different
  workers.
- Full suite run both serially and under `-n auto`: 89/89 passing either way, `-n auto` measurably
  faster despite real service round-trips.
- Every existing test file converted (consumer, API, dagster_pipeline, common/feature_flags) with zero
  changes to test *assertions* — only fixture wiring changed, confirming the conversion didn't alter
  what was actually being verified.
