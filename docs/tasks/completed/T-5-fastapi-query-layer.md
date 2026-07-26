# [done] FastAPI query layer + JWT RS256 auth (component-3) — id: T-5

Added: 2026-07-26
Completed: 2026-07-26
Notes: Feature doc written first (docs/features/fastapi-query-layer.md), per create-feature workflow.
Verified current FastAPI/PyJWT/rate-limiting/hashing best practices via web research before and during
implementation — this changed the plan twice: dropped slowapi (its internals hit a Python 3.14
deprecation warning) in favor of a small custom Redis-backed pure-ASGI RateLimitMiddleware, and dropped
bcrypt in favor of Argon2id (current OWASP default) for password hashing.
Shipped: JWT RS256 helpers with jti/exp, Redis refresh-token store (single-use, rotated), Redis
revocation blocklist, pure-ASGI security-headers + audit-log middleware (BaseHTTPMiddleware avoided for
perf/contextvars reasons), global exception handler with no internal leakage, GET /trades with
filters, POST /auth/login|refresh|logout, /metrics via prometheus-fastapi-instrumentator.
Added `filterwarnings = ["error::DeprecationWarning", ...]` to pytest config project-wide so deprecated
API usage surfaces immediately instead of silently accumulating.
16 new tests (6 JWT security-property tests including hand-forged alg:none/HS256-confusion attacks,
10 endpoint tests via httpx.AsyncClient + ASGITransport against SQLite in-memory + fakeredis).
36/36 tests passing project-wide, ruff clean.
Feature doc: docs/features/fastapi-query-layer.md
