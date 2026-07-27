# [done] Dagster cold-storage archival job (component-6) — id: T-8

Added: 2026-07-26
Completed: 2026-07-26
Notes: Feature doc written first (docs/features/dagster-archival.md), per create-feature workflow.
Shipped: an `archived` boolean column on Trade (common/db_models.py), pure archival logic
(dagster_pipeline/archival.py: batch pending trades, JSON-serialize, compress with 3.14 stdlib
compression.zstd, write to archive/, mark rows archived only after the write succeeds), and a thin
Dagster @asset wrapper (dagster_pipeline/definitions.py) with the DB engine injected via a
ConfigurableResource — same DI reasoning as api/main.py's create_app() — so dg.materialize() can swap
in SQLite in-memory and exercise the real asset/resource wiring in tests, not just the extracted logic.
Confirmed dg.materialize() actually works in this environment before committing to that design.
Verified compression.zstd works on the installed 3.14.6 interpreter before relying on it.
9 new tests (7 pure-logic against SQLite in-memory, 2 through the actual @asset via dg.materialize()).
69/69 tests passing project-wide, ruff clean, pip-audit clean.
Feature doc: docs/features/dagster-archival.md
