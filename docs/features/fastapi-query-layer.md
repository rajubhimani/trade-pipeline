# Feature: FastAPI query layer + JWT RS256 auth

Status: shipped
Task: docs/tasks/completed/T-5-fastapi-query-layer.md

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
- Security middleware stack: CORS (explicit origins only), security headers, Redis-backed rate
  limiting, structlog audit logging on `/auth/*`, global exception handler that never leaks internals.
- `/metrics` endpoint via prometheus-fastapi-instrumentator.

Out:
- Any UI/frontend — API only.
- OAuth2 / third-party identity providers — this is a self-contained RS256 JWT implementation, per the
  plan's Week 5 track.
- The enrichment service calls (component 4, T-6) — `GET /trades` returns raw stored trade rows only,
  no enrichment fan-out yet.
- Real user registration/management — one hardcoded demo account
  (`src/trade_pipeline/api/auth/users.py`) is enough to exercise the full auth flow; building a real
  user system is out of scope for this project's focus (pipeline + security hardening).

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
- Security headers AND audit logging use **pure ASGI middleware** (`api/middleware.py`), not
  `starlette.middleware.base.BaseHTTPMiddleware` — confirmed via research that `BaseHTTPMiddleware`
  wraps every request in an extra response-streaming layer costing ~1.8x throughput versus pure ASGI,
  plus known `contextvars`/background-task propagation issues, because it runs the inner app in a
  separate anyio task. Both of these middlewares run on every request, so the pure-ASGI form was
  worth the extra verbosity. See `../DECISIONS.md`.
- Global exception handler returns `{"detail": "..."}` only, logs full detail internally via
  `structlog` — matches the plan's "never leak internals" requirement. 422 validation errors are
  overridden the same way (default FastAPI verbose validation responses reveal field names/types).
- Rate limiting: **not** `slowapi` — its own internals call the now-deprecated
  `asyncio.iscoroutinefunction` (slated for removal in 3.16), which surfaced immediately as a
  `DeprecationWarning` under Python 3.14 once `filterwarnings = ["error::DeprecationWarning"]` was
  added to the test config. Replaced with a small Redis-backed pure-ASGI `RateLimitMiddleware`
  (`api/rate_limit.py`) using the same `INCR` + `EXPIRE` fixed-window pattern the plan's own Week 6-7
  system-design track recommends for a rate limiter — atomic without needing a Lua script, since
  `INCR` on a new key is itself atomic (exactly one caller ever observes the 0→1 transition). This is
  also Redis-backed rather than slowapi's default in-process storage, so it's correct across multiple
  API worker processes, not just one. Stricter limit on `/auth/*` (10/minute) than `/trades`
  (100/minute) to specifically slow brute force.
- Password hashing: Argon2id (`argon2-cffi`), not bcrypt — current OWASP-recommended default for new
  applications (bcrypt is still fine but no longer the default recommendation; passlib is confirmed
  unmaintained since 2020). See `api/auth/users.py`.

## Python version notes

No 3.12+/3.14-only syntax required for this feature — targets the full 3.11–3.14 range. Will check
`../PYTHON_VERSION_NOTES.md` before using any newer typing syntax in request/response models.

## Testing plan

- Unit tests for the JWT encode/decode helpers (valid token round-trip, expired token rejected, wrong
  algorithm rejected, missing `exp` rejected, `alg:none` attack rejected, RS256→HS256 confusion attack
  rejected — the latter two hand-forged since PyJWT's own `encode()` now refuses to build them) —
  6 tests, no FastAPI app needed.
- `httpx.AsyncClient` + `ASGITransport` (current FastAPI-recommended pattern, confirmed via research —
  supersedes `starlette.testclient.TestClient` for genuine async tests) against an app built via
  `create_app()` with a SQLite in-memory engine (`StaticPool` + `check_same_thread=False`, needed so
  multiple sessions share the same in-memory DB) and `fakeredis.FakeRedis`. 10 endpoint tests: login
  success/wrong-password/unknown-user, refresh without cookie / rotates-and-invalidates-old, logout
  revokes access token, trades without-token/with-token/filter-by-symbol/respects-limit.
- `filterwarnings = ["error::DeprecationWarning", "error::PendingDeprecationWarning"]` added to
  `pytest.ini_options` project-wide during this feature's build — caught the slowapi deprecation
  warning immediately rather than letting it linger silently (see Design section, and
  `docs/CODING_STANDARDS.md`).
- 36/36 tests passing project-wide, ruff clean. A real Docker Compose smoke test against actual
  Postgres/Redis is still deferred to the project-wide end-to-end task (same deferral as
  producer/consumer).
