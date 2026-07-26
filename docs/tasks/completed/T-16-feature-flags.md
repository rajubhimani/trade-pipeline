# [done] DB-backed feature flags + wire enrichment into GET /trades (component-3) — id: T-16

Added: 2026-07-26
Completed: 2026-07-26
Notes: Not from the original plan — added mid-session at explicit request for a feature-flag system
that toggles via a database update, not env vars/redeploys. Closes a scope gap noted in every
enrichment-related doc since T-6: enrichment was built/tested standalone but never wired into the live
API. Feature doc written first (docs/features/feature-flags.md), per create-feature workflow.
Shipped: `feature_flags` Postgres table (source of truth), common/feature_flags.py (is_enabled/
set_enabled, async, no caching layer — see docs/DECISIONS.md), GET/PATCH /admin/feature-flags/{name}
(convenience API, same JWT auth as /trades — direct DB row writes work identically and are tested
explicitly to prove the table is the real source of truth), and enrichment_enabled wired into
GET /trades (enrichment field always present in the response shape, null when the flag is off).
Enrichment services/breakers live on app.state, not created per request, so circuit-breaker state
actually persists across requests.
12 new tests (5 feature-flags unit, 4 admin endpoint, 3 trades+enrichment integration including the
direct-DB-write case). 81/81 tests passing project-wide, ruff clean, pip-audit clean.
Feature doc: docs/features/feature-flags.md
