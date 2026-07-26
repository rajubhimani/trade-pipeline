# Feature: Dagster cold-storage archival job

Status: shipped
Task: docs/tasks/completed/T-8-dagster-archival.md

## Problem / motivation

Component 6 / the cold-storage half of Layer 3 (`../ARCHITECTURE.md`) — the plan's Week 6-7 project
track calls for a second write path in the consumer: "every 1000 trades, batch them into a JSON file,
compress with `compression.zstd` (Python 3.14 stdlib), and write to a local `archive/` folder
(simulating S3)." `../ARCHITECTURE.md` already decided this batching should be a scheduled Dagster
asset/job rather than living inline in the consumer's per-message loop — this feature builds that.

## Scope

In:
- A Postgres schema addition: an `archived` boolean column on `Trade` (`common/db_models.py`), so the
  archival job can find "not yet archived" rows without a separate high-water-mark table.
- `dagster_pipeline/archival.py` — the pure archival logic (query pending rows, serialize to JSON,
  compress with `compression.zstd`, write to `archive/`, mark rows archived) as a plain testable
  function, wrapped by a thin `@asset` for Dagster.
- A `ScheduleDefinition` running the asset periodically, and a `Definitions` object wiring
  asset+schedule together so `dagster dev` can run it standalone.

Out:
- Real S3 (`archive/` is a local directory standing in for it, per the plan's own framing —
  "simulating S3").
- The daily aggregation job over archived data (dedup hit rate trends, volume per broker) —
  tracked separately as `T-13` in the backlog, depends on this feature existing first.
- Changing the consumer's write path — the consumer still writes every trade to Postgres unconditionally
  (T-4); this feature only adds a second, separate, scheduled batch job reading from that same table.

## Design

- **Why `archived` boolean, not a high-water-mark table**: simpler to reason about and query
  (`WHERE archived = false ORDER BY id LIMIT :batch_size`), and self-correcting if a run fails
  partway — a high-water-mark advanced optimistically before confirming a write could skip rows on
  crash, whereas an `UPDATE ... SET archived = true` only happens after the compressed file is
  successfully written.
- **Why Dagster, not inline in the consumer**: see `../ARCHITECTURE.md` — this is scheduled/triggered
  batch materialization with its own observability (Dagster's UI shows run history, materialized
  asset metadata like compression ratio), which is a different shape of problem than the consumer's
  tight per-message loop.
- **Batch size cap (1000)**: matches the plan's own number exactly ("every 1000 trades"); also bounds
  how much work a single scheduled run does, so a burst of pending rows drains over a few runs instead
  of one run holding a long-running transaction.
- **Compression**: `compression.zstd` (3.14 stdlib) as the primary path, with the `zstandard` PyPI
  package as the documented 3.11–3.13 fallback import — per
  `../PYTHON_VERSION_NOTES.md`'s rule of writing the newest-native form with a one-line fallback
  comment, not two live code paths.
- **Separation of pure logic from the `@asset` decorator**: same pattern as the Temporal activities in
  `../features/async-enrichment.md` — the actual archival function is a plain Python function taking a
  DB session and returning a result object, callable/testable with zero Dagster runtime. The `@asset`
  is a thin wrapper that calls it and returns Dagster-shaped metadata (row count, compression ratio) for
  the Dagster UI.
- **DB engine injected via a Dagster resource (`DbEngineResource`), not loaded from config inside the
  asset**: same DI reasoning as `api/main.py`'s `create_app()` factory — lets `dg.materialize()` swap
  in a SQLite in-memory engine for tests, so the *actual* asset/resource wiring gets exercised end to
  end, not just the extracted `archive_pending_trades` logic in isolation. Confirmed working via a real
  `dg.materialize()` call before committing to this design.

## Python version notes

`compression.zstd` is 3.14-only (stdlib); see `../PYTHON_VERSION_NOTES.md`. This is one of the few
places in the codebase that actually *uses* a 3.14-exclusive stdlib module in the primary code path
(most other version-gated choices in this project are syntax, not new stdlib modules) — the fallback
comment notes `zstandard` (PyPI) as the pre-3.14 equivalent import, not duplicated as live code.

## Testing plan

- 7 tests in `tests/dagster_pipeline/test_archival.py` against SQLite in-memory with seeded `Trade`
  rows (same style as `tests/consumer/test_postgres_sink.py`): empty-pending-rows clean no-op,
  archives + writes a compressed file, archived rows excluded from a second run, batch-size cap
  respected, archive file round-trips via `read_archived_batch`, and `ArchiveResult.compression_ratio`
  correctness (including the zero-division guard).
- 2 tests in `tests/dagster_pipeline/test_definitions.py` run the **actual `@asset`** through
  `dg.materialize()` — confirmed working in this environment, so this covers the real Dagster
  resource-injection wiring, not just the extracted logic (same bar as the Temporal workflow tests in
  `../features/async-enrichment.md`).
- 69/69 tests passing project-wide, ruff clean, pip-audit clean.
