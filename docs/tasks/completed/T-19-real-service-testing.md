# [done] Real Postgres/Redis in tests, xdist parallelism (testing) — id: T-19

Added: 2026-07-26
Completed: 2026-07-26
Notes: Not from the original plan — explicit request to remove SQLite/fakeredis and always test
against real services in Docker, with pytest-xdist for parallelism. Feature doc written first
(docs/features/real-service-testing.md).
Shipped: tests/conftest.py (pg_engine, pg_async_engine, pg_async_session, redis_client fixtures) with
per-xdist-worker Postgres schema + Redis DB index isolation and fresh-per-test schema/flush. Converted
every DB/Redis-touching test file: tests/consumer/test_postgres_sink.py, test_dedup_consumer.py,
tests/dagster_pipeline/test_archival.py, test_aggregation.py, test_definitions.py,
tests/common/test_feature_flags.py, tests/api/conftest.py — zero changes to test assertions, only
fixture wiring. Removed aiosqlite and fakeredis dependencies entirely. Added pytest-xdist. Updated
Makefile (services-up/services-down targets, test runs with -n auto) and .github/workflows/ci.yml
(real Postgres/Redis as GitHub Actions service containers, matrixed across Python 3.11-3.14 as before).
This directly unblocked Postgres partitioning (T-18) — see that task's notes.
89/89 tests passing both serially and under -n auto (measurably faster in parallel despite real
service round-trips), ruff clean, pip-audit clean.
Feature doc: docs/features/real-service-testing.md
