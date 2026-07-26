# Feature: Operational dashboard (React, minimal)

Status: shipped
Task: docs/tasks/completed/T-23-dashboard.md

## Problem / motivation

User asked for a simple UI to operate the API from — login, view trades, toggle feature flags — not
just a passive status page. Currently the only way to interact with the API is `curl`/Swagger UI
(`/docs`).

## Scope

In: `trade-pipeline/dashboard/` — a minimal Vite + React (plain JS, no TypeScript) single-page app:
login form, trades table (with symbol/broker filter), feature-flag list with a toggle button. Calls
the existing, already-tested JSON API endpoints directly via `fetch()` — no new backend endpoints.
Built output served by FastAPI as static files at `/dashboard`.

Out:
- A component library, router, or state-management library — scope doesn't need them (see
  `../DECISIONS.md` "Minimal React... for the operational dashboard").
- TypeScript — kept to plain JS for the smallest possible setup, per explicit "as small as possible,
  no fancy" direction.
- Real-time updates (websockets/polling) — a manual "refresh" action is enough for an ops tool at this
  scope.

## Design

- **Access token in a `useState` variable, not `localStorage`**: avoids persisting a bearer token
  across page loads/tabs — an XSS-surface tradeoff deliberately made in favor of security over
  convenience (re-login on refresh) for what's an internal ops tool, not a consumer product.
- **Served by FastAPI at `/dashboard`, same origin as the API**: `vite.config.js` builds straight into
  `src/trade_pipeline/api/static/` (`outDir`) with `base: '/dashboard/'` so built asset references
  resolve correctly once mounted there — `create_app()` (`api/main.py`) mounts it last via
  `StaticFiles(..., html=True)` so it can't shadow any API route, and takes an injectable
  `dashboard_static_dir` parameter (defaulting to the real build path) so tests don't depend on
  whether the dashboard has actually been built locally (see `tests/api/test_main.py`).
- **Login → trades → flags flow**: login form posts to `/auth/login`, stores the returned token in
  state; every subsequent call (`GET /trades`, `GET`/`PATCH /admin/feature-flags/enrichment_enabled`)
  goes through an `authedFetch` helper that adds the `Authorization: Bearer` header. A manual
  "Refresh" button re-fetches trades — no polling/websockets (see Scope).
- **Built inside the Docker image, not assumed pre-built**: a dedicated `dashboard-builder` Node stage
  in the `Dockerfile` runs `npm ci && npm run build` and copies the output into the Python builder
  stage before `uv sync`, so `docker compose up`/`make up` (T-24) always serves a real, current
  dashboard build — no separate "did you remember to `npm run build`" step.

## Verification

Built and served for real against the full docker-compose stack (not just unit-tested): logged in via
the dashboard UI, viewed live trades, toggled `enrichment_enabled` and confirmed it took effect on
`GET /trades`'s `enrichment` field.

## Python version notes

Not applicable — this feature is entirely frontend/JS; the only Python-side change is a static-files
mount in `api/main.py`.

## Testing plan

No automated test suite for the frontend (out of proportion for this scope) — verified manually: built
the Vite app, served it via FastAPI, and exercised login → view trades → toggle a flag → see the effect
reflected in `GET /trades`, against the real docker-compose services.
