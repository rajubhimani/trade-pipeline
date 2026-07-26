# Feature: Dagster daily aggregation over cold storage

Status: shipped
Task: docs/tasks/completed/T-13-dagster-aggregation-job.md

## Problem / motivation

Backlog item B-2 (now T-13) proposed a daily job computing "dedup hit rate trends, volume per broker"
from the archived cold-storage files (T-8). Low priority, but a natural second Dagster asset once
archival exists — demonstrates a downstream asset in Dagster's dependency graph, not just a standalone
scheduled job.

## Scope

In: `dagster_pipeline/aggregation.py` — reads every archived batch file under `archive/`, computes
volume (summed `qty`) per broker and trade count per symbol, writes the result to
`archive/aggregates/aggregate_<timestamp>.json`. A Dagster `@asset` depending on `archived_trades`
(T-8) in the asset graph, plus a daily `ScheduleDefinition`.

Out: **"dedup hit rate"**, despite being named in the original backlog note — dropped, deliberately.
Archived files only ever contain trades that already passed Redis dedup (T-4); duplicates are dropped
before ever reaching Postgres or the archive, so there is no duplicate-vs-unique ratio left to compute
from this data. Dedup hit rate is already tracked correctly, in the right place, by the consumer's own
`dedup_hits_total`/`dedup_misses_total` Prometheus counters (T-7) — recomputing it here from data
where the duplicates have already been filtered out would be wrong, not just redundant.

## Design

- Pure function (`aggregate_archive_directory`) reads via `dagster_pipeline.archival.read_archived_batch`
  rather than duplicating the zstd+JSON round-trip — that function was factored out in T-8 specifically
  for this kind of future reader.
- Reads the *entire* `archive/` directory every run rather than tracking a high-water-mark of
  already-aggregated files — this is a daily job over what's typically a modest number of files at this
  project's scale; the added complexity of incremental aggregation isn't justified here (contrast with
  T-8's archival job, which does need a high-water-mark/`archived` flag because it runs every minute
  against a live, constantly-growing table).
- Same DB-engine-injection-via-resource pattern isn't needed here since this asset only touches the
  filesystem, not Postgres — simpler dependency shape than T-8's asset.

## Python version notes

Uses `read_archived_batch`, which already handles the `compression.zstd`/`zstandard` version split
(T-8) — no new version-gated code in this feature.

## Testing plan

- 5 pure-function tests (`tests/dagster_pipeline/test_aggregation.py`) seeding real archive files (via
  `archive_pending_trades` against SQLite in-memory, same as T-8's tests): empty directory is a clean
  no-op, volume/count aggregation correctness, aggregation across multiple archive files, output file
  written/not-written depending on whether `output_dir` is given.
- 1 `dg.materialize()` test (`test_daily_aggregate_materializes_after_archived_trades`) exercising the
  real asset dependency graph — both assets materialize together via `dg.materialize([archived_trades,
  daily_aggregate], ...)`, proving `deps=[archived_trades]` actually wires the dependency, not just
  that each asset works standalone.
- 89/89 tests passing project-wide, ruff clean.
