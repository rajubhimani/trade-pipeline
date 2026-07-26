[Index](README.md) · ← Previous: [Consumer & storage](03-consumer-and-storage.md) · Next → [Enrichment](05-enrichment.md)

---

# API & auth

**Files**: everything under [`src/trade_pipeline/api/`](../../trade-pipeline/src/trade_pipeline/api/)
**Feature doc**: [docs/features/fastapi-query-layer.md](../features/fastapi-query-layer.md)
**Tests**: [`tests/api/`](../../trade-pipeline/tests/api/) (16 tests)

## What it does

The query/serve layer, and the vehicle for the whole security-hardening track: JWT RS256 auth with
rotation and revocation, security headers, rate limiting, audit logging, and an exception handler that
never leaks internals to a client.

## App assembly

**File**: [`src/trade_pipeline/api/main.py`](../../trade-pipeline/src/trade_pipeline/api/main.py)

[`create_app(engine, redis_client, api_settings)`](../../trade-pipeline/src/trade_pipeline/api/main.py#L50)
is a **factory**, not a module-level `app` — so tests can inject a SQLite in-memory engine and a
`fakeredis` client instead of real Postgres/Redis
([`tests/api/conftest.py`](../../trade-pipeline/tests/api/conftest.py)). It wires, in order:
`CORSMiddleware` → `AuditLogMiddleware` → `SecurityHeadersMiddleware` → `RateLimitMiddleware` →
exception handlers → routers → Prometheus instrumentation.

## Request flow: login → authenticated read

```mermaid
sequenceDiagram
    participant C as Client
    participant MW as Middleware stack
    participant Auth as routes_auth.py
    participant JWT as jwt_tokens.py
    participant R as Redis
    participant Trades as routes_trades.py
    participant PG as Postgres

    C->>MW: POST /auth/login {username, password}
    MW->>Auth: login()
    Auth->>Auth: authenticate() (Argon2id verify)
    Auth->>JWT: issue_access_token(user_id, private_key)
    JWT-->>Auth: RS256 JWT (15 min, has jti)
    Auth->>R: refresh_token_store.issue(user_id)
    Auth-->>C: {access_token} + httpOnly refresh cookie

    C->>MW: GET /trades  (Authorization: Bearer <token>)
    MW->>Trades: get_current_user_id() dependency
    Trades->>JWT: decode_access_token(token, public_key)
    JWT-->>Trades: claims (sub, jti, exp)
    Trades->>R: blocklist.is_revoked(jti)?
    R-->>Trades: no
    Trades->>PG: SELECT * FROM trades WHERE ...
    PG-->>Trades: rows
    Trades-->>C: 200 [TradeOut, ...]
```

## Code references — JWT

- [`issue_access_token`](../../trade-pipeline/src/trade_pipeline/api/auth/jwt_tokens.py#L37) /
  [`decode_access_token`](../../trade-pipeline/src/trade_pipeline/api/auth/jwt_tokens.py#L48) — RS256
  only, `algorithms=["RS256"]` always passed explicitly to `jwt.decode` (never derived from the
  token's own header) — this is the fix for both the `alg:none` attack and the RS256→HS256
  algorithm-confusion attack. See [DECISIONS.md](../DECISIONS.md) "RS256 over HS256."
- [`tests/api/auth/test_jwt_tokens.py`](../../trade-pipeline/tests/api/auth/test_jwt_tokens.py) —
  both attacks are hand-forged in the test (not built via our own `jwt.encode`, since PyJWT 2.13
  itself now refuses to construct an HS256 token from a PEM-shaped key) to simulate a real external
  attacker.

## Code references — refresh & revocation

- [`RefreshTokenStore.rotate(token)`](../../trade-pipeline/src/trade_pipeline/api/auth/refresh_tokens.py#L39) —
  uses Redis `GETDEL` so validating and consuming a refresh token is one atomic round trip; single-use,
  rotated on every call.
- [`TokenBlocklist.revoke(jti, expires_at)`](../../trade-pipeline/src/trade_pipeline/api/auth/blocklist.py#L24) —
  self-cleaning: the blocklist entry's TTL equals the token's remaining lifetime, so there's nothing to
  prune.
- [`routes_auth.py`](../../trade-pipeline/src/trade_pipeline/api/routes_auth.py) — `login` / `refresh`
  / `logout` wiring all three pieces together.

## Code references — middleware & rate limiting

- [`api/middleware.py`](../../trade-pipeline/src/trade_pipeline/api/middleware.py) —
  `SecurityHeadersMiddleware` and `AuditLogMiddleware` are **pure ASGI**, not
  `starlette.middleware.base.BaseHTTPMiddleware` — see [DECISIONS.md](../DECISIONS.md) for the
  throughput/`contextvars` tradeoff that motivated this.
- [`api/rate_limit.py`](../../trade-pipeline/src/trade_pipeline/api/rate_limit.py) —
  `RateLimitMiddleware` replaces `slowapi` (dropped after its internals triggered a Python 3.14
  deprecation warning) with a small Redis-backed fixed-window `INCR`+`EXPIRE` limiter. `/auth/*` is
  limited to 10/min, `/trades` to 100/min.
- [`api/dependencies.py`](../../trade-pipeline/src/trade_pipeline/api/dependencies.py) —
  `get_current_user_id` is the auth dependency every protected route uses; `get_session` yields a
  per-request `AsyncSession` off `request.app.state.async_session_factory`.

## Code references — password hashing

- [`api/auth/users.py`](../../trade-pipeline/src/trade_pipeline/api/auth/users.py) — Argon2id via
  `argon2-cffi`, not bcrypt (current OWASP-recommended default; see
  [DECISIONS.md](../DECISIONS.md)). One hardcoded demo account — a real user system is explicitly out
  of scope (see [features/fastapi-query-layer.md](../features/fastapi-query-layer.md)).

---
[Index](README.md) · ← Previous: [Consumer & storage](03-consumer-and-storage.md) · Next → [Enrichment](05-enrichment.md)
