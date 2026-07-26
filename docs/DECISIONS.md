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

### Consumer lag measured against the current message's offset, not the committed offset
`observe_consumer_lag` computes `high_watermark - 1 - message.offset()` at the point a message is
processed, not against the consumer's last-committed offset. The committed offset would also reflect
this consumer's own commit-batching/timing behavior, muddying "is the pipeline falling behind" with
"how does this consumer commit" — measuring against the message actually being handled right now
gives a cleaner, more directly interpretable signal that moves smoothly with real throughput.

### `archived` boolean column over a separate high-water-mark table
The Dagster archival job (T-8) needs to find "not yet archived" trades. A boolean column
(`WHERE archived = false ORDER BY id LIMIT :n`) is simpler to reason about and self-correcting on
failure than a high-water-mark table: rows are only marked `archived` *after* the compressed file is
successfully written, so a crash mid-run just leaves those rows eligible for the next run — no
separate recovery logic needed. A high-water-mark advanced before confirming the write could silently
skip rows on crash.

### DB engine injected via a Dagster resource, not loaded from config inside the asset
Same reasoning as `api/main.py`'s `create_app()` factory (see above): `DbEngineResource` lets
`dg.materialize()` swap in a SQLite in-memory engine for tests, so tests exercise the real
asset/resource wiring end to end instead of only the extracted pure logic. Confirmed working via an
actual `dg.materialize()` call before committing to the design.

### Feature flags stored in Postgres, not env vars
A flag that only changes on redeploy isn't really a runtime toggle — it needs to flip without
restarting every API worker process. A `feature_flags` table read through the same per-request
`AsyncSession` already in use elsewhere gives that for free, with no separate config service and no
cache-invalidation scheme to build. No caching layer in front of the reads either: a primary-key
lookup is cheap enough that this project's request volume doesn't justify the staleness window a cache
would introduce — revisit this specific tradeoff first if it ever became a hot path at real scale.

### Kafka KRaft mode, not Zookeeper
Zookeeper-based Kafka is deprecated (removed as of Kafka 4.x) — the official `apache/kafka` image
supports KRaft (broker+controller combined in one process) natively, which is both the current
upstream direction and simpler for a single-node local dev setup: one service instead of two, no
separate Zookeeper connection string to configure or fail independently. Verified the KRaft config
actually starts cleanly and carries a real produce→consume→Postgres write end to end before adopting
it (see `docker-compose.yml`).

### Docker image versions verified against the registry, not guessed
`apache/kafka:4.3.1`, `redis:8.8-alpine`, `postgres:18.4-alpine` were each checked against Docker
Hub's registry API — confirming the pinned tag's digest matches that image's own `latest` tag — before
being written into `docker-compose.yml`, rather than assumed from memory or training-data cutoff (see
`feedback_verify_current_best_practices` in this project's standing practice). This caught a real
breaking change in the process: the Postgres 18 image changed its expected data-directory mount point
(`/var/lib/postgresql` instead of `/var/lib/postgresql/data`), which would have silently failed to
start with the old volume path.

### Kafka's native `compression.type`, not hand-rolled per-message `compression.zstd`
The source plan literally names `compression.zstd` (3.14 stdlib) for producer-side message
compression. Kafka's own `compression.type: zstd` producer config was used instead: it compresses
whole batches, which achieves a far better ratio than compressing tiny individual JSON messages one
at a time — and the consumer needs zero decompression code, since librdkafka's `Consumer`
decompresses transparently on read. The stdlib `compression.zstd` module is still used in this
codebase, just where it's actually the right tool: `dagster_pipeline/archival.py`'s batch
cold-storage files, which really do compress one large payload at a time.

### A real runtime fallback for `compression.zstd`, not just a fallback comment
`archival.py` originally had a comment noting `zstandard` (PyPI) as the 3.11–3.13 fallback for
`compression.zstd` (3.14 stdlib) without actually implementing it — this broke 3 of 4 legs of the CI
matrix the moment it started running (`ModuleNotFoundError: No module named 'compression'`). Fixed
with a real `try`/`except ImportError` shim wrapping `zstandard`'s `ZstdCompressor`/`ZstdDecompressor`
to match the stdlib module's `compress()`/`decompress()` API, and added `zstandard` as a
`python_version < '3.14'` marker dependency. Lesson: the project's general policy (write the
newest-native form + a one-line fallback *comment*) is correct for syntax differences, which don't
break imports — it is not sufficient for a genuinely version-gated *module*, where an unconditional
import breaks collection entirely on unsupported versions. Verified locally against all four Python versions
(`uv run --python 3.11/3.12/3.13/3.14 --isolated pytest`) before trusting the fix, not just re-pushed
and hoped.
