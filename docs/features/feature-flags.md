# Feature: DB-backed feature flags

Status: shipped
Task: docs/tasks/completed/T-16-feature-flags.md

## Problem / motivation

The enrichment module (T-6) was built and tested standalone but never wired into the live `GET
/trades` endpoint — every feature doc up to this point noted that as an explicit scope cut. Wiring it
in unconditionally would surprise existing API consumers with a new response shape; wiring it behind a
flag that only flips on redeploy (an env var) doesn't match how flags are actually used in production —
they need to flip at runtime, without restarting every API worker.

## Scope

In:
- A `feature_flags` Postgres table (`common/db_models.py`) — the actual source of truth, not env vars.
- `common/feature_flags.py` — `is_enabled`/`set_enabled`, plain async functions reading/writing through
  the same per-request `AsyncSession` already in use elsewhere (no separate connection/resource).
- `GET/PATCH /admin/feature-flags/{name}` — a convenience API for toggling a flag, protected by the
  same JWT auth as `/trades`. Not the *only* way to change a flag: a direct
  `UPDATE feature_flags SET enabled = true WHERE name = ...` against Postgres works identically, since
  the table itself is the source of truth, not the API.
- Wiring the `enrichment_enabled` flag into `GET /trades`: when on, every returned trade gets an
  `enrichment` field (null when off) populated by the hand-rolled enrichment fan-out (T-6) against two
  demo mock services.

Out:
- Role-based access control for the admin endpoints — they use the same auth as every other protected
  route; a real deployment would add an actual admin role. Out of scope here, same reasoning as the
  demo user store in `api/auth/users.py`.
- A caching layer in front of the flag reads — see Design.
- Per-user/percentage-rollout targeting — this is a simple global on/off switch, not a full
  flag-management product.

## Design

- **DB-backed, not env-var-backed**: a flag that only changes on redeploy isn't really a runtime
  toggle. Storing it in Postgres and reading it through the request's existing `AsyncSession` means a
  flag flip takes effect on the very next request, across every API worker process, with zero
  additional infrastructure (no separate config service, no Redis pub/sub for invalidation).
- **No caching**: every flag read is a real primary-key lookup (`session.get(FeatureFlag, name)`) —
  cheap enough that this project's request volume doesn't justify the staleness-window complexity a
  cache-invalidation scheme would add. If this ever became a hot path at real scale, that's the
  documented first thing to reconsider.
- **Missing row is "not yet toggled," not an error**: `is_enabled` falls back to `DEFAULT_FLAGS` (a
  plain dict) when no row exists — a flag starts disabled until someone explicitly turns it on, either
  through the admin API or a direct DB write.
- **`enrichment` field always present, `None` when the flag is off**: the response shape doesn't
  change based on flag state — a client parsing the response doesn't need to branch on whether the key
  exists, just on whether its value is null.
- **Enrichment services/breakers live on `app.state`, not created per request**: circuit-breaker
  failure state needs to persist across requests to mean anything (see `docs/features/async-enrichment.md`)
  — creating fresh breakers per request would make the circuit breaker permanently `CLOSED` regardless
  of upstream failures, defeating its purpose.

## Python version notes

No version-gated syntax; targets the full 3.11–3.14 range per `../PYTHON_VERSION_NOTES.md`.

## Testing plan

- `tests/common/test_feature_flags.py` (5 tests): missing-row defaults, set-then-read round trip,
  update of an existing row, returned row shape.
- `tests/api/test_routes_admin.py` (4 tests): unknown flag defaults to disabled via the API, PATCH
  enables/disables, admin endpoints require auth.
- `tests/api/test_routes_trades.py` (+3 tests): `enrichment` is `None` when the flag is off,
  `enrichment` is populated when toggled on **through the admin API**, and — the specific case this
  feature was built for — `enrichment` is populated when the flag is toggled on via a **direct DB row
  write**, with no admin API call at all, proving the table is genuinely the source of truth and not
  just something the API happens to also read.
- 81/81 tests passing project-wide, ruff clean, pip-audit clean.
