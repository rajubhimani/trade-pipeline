# Decisions log (ADR-lite)

One entry per non-obvious technical choice. Written so answers like "why Redis not DB for dedup" are
never re-derived from scratch — pulled from here, verified against current code before quoting.

---

### Redis SETNX for dedup, not a DB unique constraint
Redis in-memory ops are O(1) and sub-millisecond, needed to keep pace with per-event Kafka consumption
without becoming the bottleneck. A DB unique-constraint approach works but adds a round trip and a
failed-insert-as-control-flow pattern per duplicate, which is slower and noisier in logs. TTL (`EX 300`)
bounds memory since we only need a 5-minute dedup window.

### RS256 over HS256 for JWT
Asymmetric signing means only the auth service holds the private key; any service that only needs to
*verify* tokens (the query API) only needs the public key. HS256 would require distributing the shared
secret to every verifying service, which is a bigger blast radius if one is compromised.

### Postgres (hot) + local zstd archive (cold), not ClickHouse
The prep-plan's Q5 model answer uses ClickHouse for the hot path at real scale. This project is a
learning/demo build at low volume, so Postgres is enough to be genuinely queryable and keeps the
dependency count down; the README documents ClickHouse as the stated "what I'd change at 10x scale"
answer, per the plan's mock-interview guidance.

### Temporal for enrichment orchestration, not the ingestion hot path
See `ARCHITECTURE.md`. Short version: Temporal per-workflow overhead is fine for a bounded,
multi-service enrichment call with retries; it is the wrong tool for a tight per-Kafka-message loop
handling every trade event.

### Dagster for cold-storage batching, not live consumption
Same reasoning in the other direction — Dagster assets are for scheduled/triggered batch materialization
with observability, not per-message stream processing.

### uv over pip/poetry
Single fast tool for Python version management (3.11–3.14 side by side), dependency resolution, and
lockfiles. Matches the project's explicit goal of running/comparing multiple Python versions.

### Sync psycopg for the consumer's Postgres sink, async asyncpg for the API
The consumer's Kafka poll loop (`confluent_kafka.Consumer.poll()`) is a plain blocking loop, not an
asyncio event loop — an async DB driver there would need its own bridged event loop for zero benefit.
The FastAPI query layer actually runs an event loop, so async SQLAlchemy + `asyncpg` earns its keep
there. Same `Trade` ORM model backs both (`common/db_models.py`) — SQLAlchemy table definitions are
engine-agnostic; only the Session/Engine layer differs.

### Argon2id over bcrypt for password hashing
Checked current guidance while building the demo login: Argon2id (`argon2-cffi`) is the current
OWASP-recommended default for new applications. bcrypt is still fine and widely used, but is no longer
the default recommendation; `passlib` (a common bcrypt wrapper) is confirmed unmaintained since 2020
and was ruled out on that basis alone.

### Pure ASGI middleware over `BaseHTTPMiddleware` for security headers + audit logging
`starlette.middleware.base.BaseHTTPMiddleware` is the tutorial-standard choice, but it wraps every
request in an extra response-streaming layer that measurably costs throughput (~1.8x vs pure ASGI) and
has known `contextvars`/background-task propagation issues, because it runs the inner app in a
separate anyio task. Both of these middlewares run on every single request, so the extra verbosity of
writing them as plain ASGI callables (`api/middleware.py`) was worth it. `CORSMiddleware` itself is
left as-is (already pure ASGI internally).

### Custom Redis-backed rate limiter over `slowapi`
Started with `slowapi` (the common choice for FastAPI rate limiting), but its own internals call the
now-deprecated `asyncio.iscoroutinefunction` (slated for removal in Python 3.16) — this surfaced
immediately as a test failure once `error::DeprecationWarning` was added to pytest's `filterwarnings`
(see `CODING_STANDARDS.md`), and isn't something fixable from the outside. Replaced with a small
Redis-backed pure-ASGI `RateLimitMiddleware` (`api/rate_limit.py`) using fixed-window `INCR` + `EXPIRE`
— the same pattern the plan's own Week 6-7 system-design track recommends for a rate limiter. This is
also Redis-backed rather than slowapi's default in-process storage, so it's correct across multiple
API worker processes rather than under-counting, which is a real limitation worth knowing about even
if this project only runs one worker.
