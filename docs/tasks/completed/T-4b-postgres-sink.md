# [done] Postgres sink writer for consumer (component-2) — id: T-4b

Added: 2026-07-26
Completed: 2026-07-26
Notes: Implemented as **sync** SQLAlchemy + psycopg (v3) — not async/asyncpg as originally noted here.
Correction: the consumer's poll loop is a plain blocking confluent-kafka loop (no event loop running),
so an async driver would need its own event loop bridged in awkwardly for no benefit; async SQLAlchemy
is reserved for the FastAPI query layer (T-5) which actually runs one. See
docs/features/dedup-consumer.md and postgres_sink.py docstring for full rationale.
Wired as the `sink` callable in DedupConsumer via `run_consumer.__main__`; offset commit already only
happens after `DedupConsumer.process_message` returns without raising (dedup_consumer.py, unchanged).
Adds a DB-level unique constraint on (broker_id, trade_id) as defense-in-depth behind Redis dedup —
raises `DuplicateTradeError` on conflict rather than silently swallowing it.
3 new unit tests (tests/consumer/test_postgres_sink.py) against SQLite in-memory — 20/20 tests passing
project-wide.
Feature doc: docs/features/dedup-consumer.md
