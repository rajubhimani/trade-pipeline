# Decisions log (ADR-lite)

One entry per non-obvious technical choice. Written so answers like "why Redis not DB for dedup" are
never re-derived from scratch — pulled from here, verified against current code before quoting.

---

### `confluent-kafka`, not `kafka-python`
`confluent-kafka` is a thin binding over `librdkafka` (the C client Confluent itself maintains) —
`kafka-python` is a pure-Python reimplementation of the wire protocol. That difference shows up in
exactly the places this project cares about:

- **Throughput/latency** — `librdkafka` batches, compresses, and pipelines at the C layer;
  `kafka-python`'s pure-Python protocol handling is measurably slower per message, which matters for
  a producer intentionally simulating N broker feeds plus ~5% duplicate load (`producer/fake_trades.py`).
- **Delivery semantics this project actually exercises** — manual offset commit only after a
  successful Postgres write (`consumer/dedup_consumer.py`) needs precise, well-tested control over
  `commit()`/auto-commit behavior. `librdkafka`'s consumer group and offset management is the
  reference implementation every other client (including `kafka-python`) is validated against, not
  the other way around.
- **Native compression** — `compression.type` (see "Kafka's native `compression.type`" below) is a
  `librdkafka` broker-negotiated feature; getting the same behavior in `kafka-python` means more
  manual plumbing.
- **Maintenance** — `kafka-python` went through a multi-year stretch with no releases before recent
  revival; `confluent-kafka` ships in lockstep with `librdkafka` and current Kafka broker features.

`kafka-python`'s real advantage — pure Python, no C toolchain/wheel to install — isn't a constraint
here (the Dockerfile already builds from a full Python base image), so there's nothing on the other
side of the trade-off to weigh against it.

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

### Real Postgres/Redis in tests, not SQLite/fakeredis
This project ran its whole test suite against SQLite in-memory and `fakeredis`/hand-rolled fakes for
its first several components — fast, no Docker needed, and genuinely sufficient for logic that never
touched a Postgres- or Redis-specific feature. That changed by explicit request: tests now run against
the real `postgres:18.4-alpine` and `redis:8.8-alpine` containers this project's own
`docker-compose.yml` already defines (`docker compose up -d postgres redis` before `pytest`).

This is what actually unblocked Postgres partitioning (see `docs/features/postgres-partitioning.md`):
partitioning requires a composite `(id, timestamp)` primary key, which SQLite cannot autoincrement at
all — forcing that onto a schema also used by SQLite-backed tests would have meant rewriting every
test that constructs a `Trade` row without an explicit `id`. Testing against real Postgres removed the
conflict entirely; there's one schema, not two dialects to keep compatible.

Parallelized with `pytest-xdist` (`-n auto`) to offset the cost of talking to real services — each
worker gets its own Postgres schema (`search_path`) and Redis logical DB index, both derived from the
xdist worker id, so workers never see each other's data despite sharing the same containers. Within a
single worker, each test gets a fresh schema (drop/recreate) or a flushed Redis DB, so tests remain
independent of execution order.

CI (`.github/workflows/ci.yml`) runs real Postgres/Redis as GitHub Actions `services:` containers
(well-supported, exposed to the runner's `localhost` automatically) — not a hand-rolled
docker-compose-in-CI setup. Kafka is deliberately not included as a CI service: producer/consumer code
that talks to a real broker remains manually verified (see `docs/tasks/completed/T-17-docker-image-upgrades.md`),
since Kafka has no first-party GitHub Actions service support and is meaningfully more fragile to run
as an ad-hoc container than Postgres/Redis.

### `pydantic-settings`, not hand-rolled dataclass + `os.environ.get()` + a TOML file
Configuration loading (`common/config.py`, `api/settings.py`) originally hand-rolled env-var reading
over a `config.toml` file for defaults. Replaced with `pydantic_settings.BaseSettings`: typed
validation, `.env` file support, and precedence (real env var > `.env` > default) built in rather than
implemented ad hoc. `.env`/environment variables is also the far more common industry pattern for
per-environment application config (the 12-factor app convention) — TOML remains the right choice for
non-secret, checked-in tool/build config (`pyproject.toml` itself), just not for this. `config.toml`
was removed entirely rather than kept as a second, now-redundant config source.

`ApiSettings` (the value object holding actual key *content*) was deliberately kept separate from the
new `ApiEnvSettings` (the class that reads paths/CORS from the environment) — tests construct
`ApiSettings` directly with an in-memory-generated ephemeral RSA keypair (see `tests/api/conftest.py`),
the same dependency-injection pattern already used elsewhere in this codebase (`create_app` vs
`build_production_app`). Only `load_api_settings()`, the real production path, touches
`ApiEnvSettings` at all.

### One Dockerfile / one image for every entrypoint, not four
Producer, consumer, API, and Dagster all share the exact same `pyproject.toml`/`uv.lock` dependency
set — a single multi-stage image with the entrypoint selected via `command:` override per
docker-compose service is the correct pattern here, confirmed via research to be the standard
recommendation (not an anti-pattern) for a single-package project with multiple entrypoints. Four
near-identical Dockerfiles would only add build/maintenance overhead with no real benefit at this
project's scale.

### `--locked`, not `--frozen`, in the Dockerfile's `uv sync` calls
`--frozen` (older, still-common guidance) skips lockfile validation silently — a stale `uv.lock`
relative to `pyproject.toml` would build anyway. `--locked` fails the build outright in that case,
which is what you actually want for a CI/production image: a lockfile drift should be a loud build
failure, not a silent behavioral mismatch shipped to production.

### `docker-compose.yml` runs the full stack, not just infrastructure (T-24)
Superseded the earlier decision to keep the app on `uv run` and compose to infra-only — `make up`
(`docker compose up -d --build`) now brings up everything: `producer`, `consumer`, `api`, and `dagster`
services built from the one `Dockerfile` (`build: .`, entrypoint selected via `command:`), alongside
Kafka/Redis/Postgres. Two supporting one-shot services close the gaps a plain `docker run` left open:
- `keys-init` generates the JWT RS256 keypair into a shared `keys` named volume (`scripts/generate_keys.py`,
  using `cryptography` directly — no host shell/`openssl` available for a container-only volume).
- `migrate` creates the schema + partitions before `api`/`consumer` start, so the two don't race each
  other into calling `init_schema`/`ensure_partitions` implicitly.

All three infra services get real healthchecks (`pg_isready`, `redis-cli ping`,
`kafka-broker-api-versions.sh`), and app services gate on `condition: service_healthy` /
`service_completed_successfully` rather than compose's default (and insufficient) "container started"
ordering. `uv run` locally is still fully supported and unaffected — this only changes what
`docker compose up` / `make up` does.

**Bug caught during verification:** `ApiEnvSettings`'s default key paths (`api/settings.py`) were
computed from `Path(__file__).parent.parent.parent.parent`, assuming the source tree's on-disk layout.
That assumption broke under `uv sync --no-editable` (the Dockerfile's install mode) — `__file__`
resolves inside `.venv/lib/python3.14/site-packages/trade_pipeline/...` at runtime, not `/app/src/...`,
so the default silently pointed at a path with no relation to the `keys` volume mount, and the `api`
container crash-looped on startup (`FileNotFoundError`) rather than failing loudly at the point of the
bad assumption. Fixed by making the default a plain relative path (`Path("keys")`), resolved against
the process's cwd — both `uv run` (repo root) and every compose service (`WORKDIR /app`) launch with
the right cwd already, so no `__file__` introspection is needed at all.

### DLQ publish-then-commit, not the original skip-without-commit
The original consumer failure handling (log, skip, don't commit) is correct for *transient* failures —
Kafka redelivers the message from the last committed offset on restart, and it eventually succeeds.
It's wrong for *permanent* failures (a message that will never process successfully), which just
generate the same failure forever, on every restart. Publishing the failed message's envelope to a
`{topic}-dlq` topic and then committing the original offset anyway captures it durably (a human or a
replay tool can act on it later) while letting the pipeline keep moving — matching the plan's own
system-design guidance ("Kafka broker down → consumer lag alert → DLQ fills → ops page"). If the DLQ
publish itself fails, the original offset is deliberately *not* committed — falling back to the old
redeliver-on-restart behavior is safer than silently losing the message when the DLQ is unavailable.

### Minimal React (Vite, plain JS, no extra libraries) for the operational dashboard
The dashboard's actual scope — a login form, a trades table, a feature-flag toggle — has no
state-management complexity, component reuse, or routing that *requires* React; vanilla JS would be
technically sufficient. Chosen anyway because this is an interview-prep project where demonstrating
current, idiomatic React usage has real value, and because it's the common real-world default for
anything UI-facing even when the first version is simple. Kept deliberately minimal to match the
actual scope: Vite's plain JS template (no TypeScript, no router, no state-management library, no UI
component library), a single component file calling the already-built, already-tested JSON API
endpoints directly via `fetch()`.

### Alembic for schema DDL, not `Base.metadata.create_all` (T-25)
Schema setup started as `Base.metadata.create_all(engine)`, called from both the consumer's own
startup and the one-shot `migrate` compose service (`scripts/migrate.py`). That works for a schema
that only ever gets created once, but has no story for changing a schema that already has data in
it — `create_all` only issues `CREATE TABLE IF NOT EXISTS`; it never diffs or alters an existing
table. Alembic replaces that with versioned, reviewable revisions with an explicit `upgrade`/
`downgrade` path (`migrations/versions/`).

The initial revision (`0001_initial_schema.py`) is hand-written to match `common/db_models.py`
exactly, not autogenerated — autogenerating against an already-populated database would have diffed
against an *empty* one and produced nothing. Later schema changes should use
`make db-revision m="..."` (`alembic revision --autogenerate`) and always be reviewed before commit:
autogenerate can't detect column renames or some type changes, and would emit a drop+add instead.

Partition DDL (`common/partitioning.py`) deliberately stays outside Alembic. It creates a DEFAULT
catch-all partition plus the current and next calendar month's partitions — "current/next month" is
a moving target that can't be expressed as a static, one-time revision, so it stays as the existing
idempotent runtime call (`ensure_partitions`, run right after `alembic upgrade head` in
`common/migrations.upgrade_to_head`).

`migrations/env.py` resolves its connection from `common/config.load_config()` (the same
`POSTGRES_DSN` every other entrypoint reads) rather than a separate URL hardcoded in `alembic.ini`,
and reuses an already-open engine when one is passed in via `config.attributes["connection"]` — so
`postgres_sink.init_schema` and `scripts/migrate.py` don't open a second Postgres connection just to
migrate.

`tests/conftest.py`'s `pg_engine` fixture was also switched from its own `Base.metadata.create_all`
call to `upgrade_to_head` — tests were building the schema a second, independent way, which defeats
the point of having one versioned source of truth. It still does `Base.metadata.drop_all` plus an
explicit `DROP TABLE IF EXISTS alembic_version` per test (Alembic has no "wipe and reset" command of
its own) so each test starts from a genuinely blank schema and replays the real migration path, not
a fixture-only shortcut.

### Compatible-release (`~=`) version pins, not bare `>=`
Every dependency in `pyproject.toml` used a bare floor (`fastapi>=0.115`) with no upper bound. `uv
lock` resolves each of those to the *highest* version on PyPI satisfying it — with no ceiling, that
silently includes the next major release the moment it ships, which is exactly the "ran `uv lock
--upgrade`, something got removed/renamed/deprecated, code breaks with no warning" scenario this
pin scheme exists to prevent. (This had already happened once in practice: `redis>=5.2` had resolved
all the way to 8.0.1 by the time this was written — three major versions past what was originally
tested against.)

Switched every entry to PEP 440's "compatible release" operator (`~=`), which keeps the same floor
behavior but adds an implicit ceiling at the next major version — `sqlalchemy[asyncio]~=2.0` means
`>=2.0, ==2.*`, so `uv lock --upgrade` can move within 2.x freely but will never resolve 3.0 without
someone deliberately widening the pin.

Pre-1.0 packages (`fastapi`, `uvicorn`, `asyncpg`, `prometheus-client`, `zstandard`) are pinned one
level deeper — `fastapi~=0.140.0`, not `fastapi~=0.140` — because 0.x releases don't carry semver's
major/minor split; by convention (and in practice, per each project's own changelog) a 0.x *minor*
bump is where breaking changes land, so the pin has to lock the minor component, not just leave "0"
fixed, to actually block them.

Every floor was also raised to match what `uv.lock` had already resolved to (not left at each
package's original, months-stale floor) — that's what's actually been running and tested; pinning a
`~=` ceiling on top of a stale floor would have meant re-resolving down to an old, unverified
version. Confirmed no-op: `uv lock` after the change reported the same 132 resolved packages at the
same versions, just with updated requirement strings.

### `confluent-kafka`, `kafka-python`, and Redpanda
`confluent-kafka` was already the client choice — it wraps `librdkafka` (higher throughput, more
mature offset/consumer-group control, native `compression.type`) rather than reimplementing the wire
protocol in pure Python like `kafka-python` does. Redpanda is a separate question — it's not a client
library, it's a broker that speaks that same Kafka wire protocol, which is exactly why `confluent-kafka`
needs zero code changes to talk to it either way.

For this project, Kafka stays the default: the whole point of the build is demonstrating real Kafka
internals (KRaft, consumer-group/offset semantics, `librdkafka`) for interview prep, and swapping the
default broker would dilute that story even though nothing else about the pipeline would need to
change. Redpanda is offered as an opt-in alternative instead (`make up-redpanda`) rather than
skipped entirely — the ops-simplicity/no-JVM pitch is a legitimate real-world tradeoff worth having
on hand to discuss, just not the right default for *this* project's purpose.

### Redpanda as an opt-in broker swap (`docker-compose.redpanda.yml`)
Considered using Compose's `profiles:` keyword for this, but `profiles:` can only include/exclude
whole services — it can't swap what a service *named* `kafka` points at. `producer`/`consumer`/
`dagster` all reference the broker purely by that service name (`KAFKA_BOOTSTRAP_SERVERS:
kafka:29092`, `depends_on: kafka`), so a `profiles:`-based approach would mean duplicating every one
of those dependent services just to point a `depends_on` at a different broker service name.

Used a Compose override file instead: `docker-compose.redpanda.yml` redefines the `kafka` service
under the *same* service name — same hostname, same internal port (`29092`) and host port (`9092`),
just `redpandadata/redpanda:v26.1.14` instead of `apache/kafka:4.3.1` and an `rpk cluster health`
healthcheck instead of `kafka-broker-api-versions.sh`. Nothing else in `docker-compose.yml` changes.
`make up-redpanda` runs `docker compose -f docker-compose.yml -f docker-compose.redpanda.yml up -d
--build`; default `make up` is untouched.

Verified against real containers, not just `docker compose config`: brought the Redpanda stack up
end to end (`producer` → Redpanda → `consumer` → Postgres, `make demo` against the API), confirmed
rows landed in Postgres, then tore down and brought the default Kafka stack back up to confirm both
paths work off the same compose file set.

### `common/migrations.py` resolves `alembic.ini` by searching parents, not a fixed offset
Caught while testing the Redpanda swap above (`migrate` exited 1 with "No 'script_location' key
found"), unrelated to Redpanda itself: `upgrade_to_head`'s original `Path(__file__).resolve().parents[3]`
assumed this file always lives 3 directories under the repo root (`src/trade_pipeline/common/`) — true
for local/editable installs, but the Dockerfile's `uv sync --no-editable` installs the package under
`.venv/lib/pythonX/site-packages/trade_pipeline/common/` instead, 4 parents from `/app` (where the
Dockerfile separately `COPY`s `alembic.ini`/`migrations/`). The wrong fixed offset pointed at a
directory with no `alembic.ini`, and `alembic.config.Config` doesn't error on a missing file — it
just produces an empty config, so the failure only surfaced later at `upgrade()` with a confusing
"No 'script_location' key found" instead of a clear "file not found".

Fixed by walking `Path(__file__).resolve().parents` looking for the first directory containing
`alembic.ini`, which finds it correctly regardless of install layout (editable vs. site-packages)
instead of assuming either one. Confirmed by rebuilding and bringing up both the Kafka and Redpanda
stacks from a clean volume — `migrate`/consumer startup schema init succeeds in both.
