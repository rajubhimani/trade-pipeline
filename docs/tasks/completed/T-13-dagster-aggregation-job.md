# [done] Daily Dagster aggregation job over cold storage (component-6) — id: T-13

Added: 2026-07-26
Completed: 2026-07-26
Notes: Feature doc written first (docs/features/dagster-aggregation.md). Scope correction while
implementing: dropped "dedup hit rate" from the original note — archived files only contain trades
that already passed dedup, so that ratio isn't recoverable from this data; already tracked correctly
by the consumer's own Prometheus counters (T-7).
Shipped: dagster_pipeline/aggregation.py (pure function reading every archived batch via T-8's
read_archived_batch, computing volume-by-broker and count-by-symbol, writing a JSON summary), and a
daily_aggregate Dagster asset with deps=[archived_trades] — a real downstream asset in the dependency
graph, not a standalone job, with its own daily ScheduleDefinition.
6 new tests (5 pure-logic, 1 dg.materialize() proving the actual asset dependency wiring works, not
just each asset standalone). 89/89 tests passing project-wide, ruff clean.
Feature doc: docs/features/dagster-aggregation.md
