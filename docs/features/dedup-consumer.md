# Feature: Consumer with Redis dedup + manual offset commit

Status: shipped
Task: docs/tasks/completed/T-4-dedup-consumer.md, docs/tasks/completed/T-4b-postgres-sink.md

## Problem / motivation

Component 2 of the project (`../ARCHITECTURE.md`). The producer intentionally emits duplicate trade
events; the consumer must drop duplicates before they reach storage, and must never lose an event on
crash (at-least-once delivery, not at-most-once).

## Scope

In: `src/trade_pipeline/consumer/dedup_consumer.py` — `DedupConsumer` class wrapping the dedup
decision + sink-write + commit sequencing, and `run_consumer()` wiring it to a real
`confluent_kafka.Consumer`.

Out: async Postgres access — the sink is sync SQLAlchemy/psycopg (see Design), not async/asyncpg; that
driver is reserved for the FastAPI query layer (T-5) which runs an actual event loop.

## Design

- Dedup check: `redis.set(key, 1, nx=True, ex=ttl)` — atomic set-if-not-exists with TTL, equivalent to
  the plan's `SETNX ... EX 300`. Returns truthy only when the key was newly created; a falsy return
  means it's a duplicate. See `../DECISIONS.md` for why Redis over a DB unique constraint.
- Offset commit is manual (`enable.auto.commit: False`) and only happens after
  `DedupConsumer.process_message()` returns successfully. If the sink write raises, the exception
  propagates out of `process_message`, the offset is *not* committed, and the message will be
  redelivered by Kafka on restart — this is the load-bearing behavior the plan calls out
  ("never auto-commit — you'd lose events on crash").
- Duplicates are still committed past (no need to redeliver something we're intentionally dropping).
- `DedupStats` tracks `processed` / `duplicates` counts and exposes `dedup_hit_rate` for the
  observability layer (T-7) to surface later.
- Postgres sink (`src/trade_pipeline/consumer/postgres_sink.py`): sync SQLAlchemy engine (`psycopg` v3
  driver, not `asyncpg` — the consumer's confluent-kafka poll loop is blocking, not asyncio, so an
  async driver would need its own bridged event loop for no benefit). Adds a DB-level unique
  constraint on `(broker_id, trade_id)` as defense-in-depth behind Redis dedup, raising
  `DuplicateTradeError` on conflict — this is a rare/alertable case, not silently swallowed, since it
  means the two dedup layers disagreed (e.g. a Redis TTL expiry + broker resend outside the window).

## Python version notes

`DedupStats` uses `@dataclass(slots=True)` (3.10+, fine across the whole 3.11–3.14 range). No
version-gated syntax otherwise.

## Testing plan

Unit tests in `tests/consumer/test_dedup_consumer.py` (4 tests) using a minimal in-memory `FakeRedis`
and `FakeMessage` — no real Kafka/Redis needed to verify dedup logic, stat tracking, and that same
`trade_id` across different `broker_id`s is correctly treated as distinct. `tests/consumer/test_postgres_sink.py`
(3 tests) uses the shared `pg_engine` fixture (real Postgres) to verify the sink persists rows and enforces the unique constraint.
20/20 tests passing project-wide. `run_consumer()` itself (real Kafka wiring end to end) is not yet
covered — needs Docker Compose up, deferred to the end-to-end smoke test task, same as the producer.
