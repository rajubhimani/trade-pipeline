# [done] Postgres range partitioning for the trades table (component-2) — id: T-18

Added: 2026-07-26
Completed: 2026-07-26
Notes: Not from the original plan — user asked directly whether the project should partition Postgres.
Feature doc written first (docs/features/postgres-partitioning.md).
Initial design kept partitioning in a standalone demo table to avoid conflicting with SQLite-based
tests (SQLite cannot autoincrement a composite primary key, which range partitioning requires).
Superseded once the test suite moved to real Postgres (T-19) — applied directly to the shared `Trade`
model instead: composite `(id, timestamp)` primary key with `Identity()` (verified this still
self-populates correctly against live Postgres despite the composite key), `postgresql_partition_by`
table option, and `common/partitioning.py` creating the actual child partitions (DEFAULT catch-all +
current/next month), wired into `postgres_sink.init_schema()`.
Verified end-to-end against the real postgres:18.4-alpine container: correct partition routing by
timestamp, out-of-range rows land in the DEFAULT partition, transparent querying via the parent table.
Feature doc: docs/features/postgres-partitioning.md
