# Feature: FastAPI query layer + JWT RS256 auth

Status: draft
Task: docs/tasks/backlog/T-5-fastapi-query-layer.md

## Problem / motivation

Component 3 of the project (`../ARCHITECTURE.md`) — the query/serve layer, and the vehicle for the
entire Week 5 security-hardening track: the plan's Q4 gap analysis calls out missing security headers,
CORS config, JWT attack-vector awareness, rate limiting, and error sanitization as the specific things
that separate a 1/5 from a 4/5 security answer. This feature is where all of that becomes real code,
not just a checklist.

## Scope

In:
- `GET /trades` — filtered read endpoint over the `trades` table populated by the consumer (component 2).
- `POST /auth/login` — issues a short-lived JWT access token (RS256) + refresh token.
- `POST /auth/refresh` — rotates the refresh token (single-use), issues a new access token.
- `POST /auth/logout` — revokes the current access token (JWT blocklist) and deletes the refresh token.
- Security middleware stack: CORS (explicit origins only), security headers, slowapi rate limiting,
  structlog audit logging on `/auth/*`, global exception handler that never leaks internals.
- `/metrics` endpoint via prometheus-fastapi-instrumentator.

Out:
- Any UI/frontend — API only.
- OAuth2 / third-party identity providers — this is a self-contained RS256 JWT implementation, per the
  plan's Week 5 track.
- The enrichment service calls (component 4, T-6) — `GET /trades` returns raw stored trade rows only,
  no enrichment fan-out yet.

## Design

- Async SQLAlchemy with the `asyncpg` driver (distinct from the consumer's sync `psycopg` sink — see
  `../features/dedup-consumer.md` for why the split exists). FastAPI dependency yields an
  `AsyncSession` per request.
- JWT: RS256 only, algorithm pinned explicitly on decode (`algorithms=["RS256"]`) — never derived from
  the token header, which is exactly the `alg:none` / algorithm-confusion attack the plan calls out.
  Access tokens short-lived (15 min); refresh tokens are random UUIDs stored in Redis with a 7-day TTL,
  single-use (rotated on every refresh), delivered as an httpOnly cookie.
- Revocation: access-token `jti` claim added to a Redis blocklist on logout, checked on every request
  via the auth dependency — JWTs are otherwise stateless and can't be individually invalidated.
  See `../DECISIONS.md` for the RS256-over-HS256 rationale.
- Security headers via `BaseHTTPMiddleware` (X-Content-Type-Options, X-Frame-Options,
  Strict-Transport-Security, Content-Security-Policy, Referrer-Policy) — chosen over per-route header
  injection so nothing can forget it; tradeoff (context-var/perf caveats of `BaseHTTPMiddleware`)
  documented in code comments once confirmed against current docs.
- Global exception handler returns `{"detail": "..."}` only, logs full detail internally via
  `structlog` — matches the plan's "never leak internals" requirement. 422 validation errors are
  overridden the same way (default FastAPI verbose validation responses reveal field names/types).
- Rate limiting via `slowapi`: stricter limit on `/auth/*` (e.g. 10/minute) than `/trades` (100/minute)
  to slow brute force specifically.

## Python version notes

No 3.12+/3.14-only syntax required for this feature — targets the full 3.11–3.14 range. Will check
`../PYTHON_VERSION_NOTES.md` before using any newer typing syntax in request/response models.

## Testing plan

- Unit tests for the JWT encode/decode helpers (valid token round-trip, expired token rejected, wrong
  algorithm rejected, missing `exp` rejected) — no FastAPI app needed for these.
- `httpx.AsyncClient` + FastAPI's test client (ASGI transport, no real server) for endpoint tests:
  login → get token → call `/trades` with it → 200; call `/trades` without a token → 401; refresh flow
  end to end (per the plan's Week 3 Saturday integration test description).
- Redis and Postgres dependencies faked/stubbed for unit tests; a real Docker Compose smoke test is
  deferred to the project-wide end-to-end task (same deferral as producer/consumer).
