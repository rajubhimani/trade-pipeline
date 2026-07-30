# Feature: Async enrichment — hand-rolled vs Temporal workflow

Status: shipped
Task: docs/tasks/completed/T-6-async-enrichment.md

## Problem / motivation

Component 4 of the project (`../ARCHITECTURE.md`) — the query API calls out to 3 mock enrichment
services in parallel to attach extra data to a trade before returning it. This is also where the
plan's Week 4 async-mastery track becomes real code: `gather()` vs `wait()` vs `TaskGroup`, timeout vs
backoff, and a hand-rolled circuit breaker are all named explicitly as "what Q3 wanted."

Per the user's explicit ask to use Temporal "wherever applicable," this is also where a second,
parallel implementation lives: the same enrichment fan-out rebuilt as a Temporal Workflow + Activities,
so both approaches are real, tested, and comparable — mirroring how
`docs/features/version-compat-demo.md` compares old vs new Python syntax, but here comparing
hand-rolled orchestration vs a durable-execution framework for the same problem.

## Scope

In:
- `enrichment/mock_services.py` — 3 fake enrichment services with configurable latency/failure, used
  by both implementations and their tests.
- `enrichment/circuit_breaker.py` — the plan's 3-state (`CLOSED`/`OPEN`/`HALF_OPEN`) circuit breaker,
  one instance per enrichment service (not shared), exactly as specified in the plan's Week 4 project
  track.
- `enrichment/hand_rolled.py` — `asyncio.gather(return_exceptions=True)` + per-call
  `asyncio.wait_for(timeout=2)` + `tenacity` retry (on timeout only, never on 4xx-equivalent errors)
  + circuit breaker per service, returning a merged dict with graceful partial results on failure.
- `enrichment/temporal_workflow.py` — the same fan-out as a Temporal `@workflow.defn` calling
  `@activity.defn` activities concurrently, with a `RetryPolicy` per activity matching the hand-rolled
  version's retry semantics (retry on timeout-shaped errors, not on non-retryable ones), and partial
  results on activity failure instead of failing the whole workflow.
- The durable per-trade dispatch path (see "Durable per-trade enrichment" below) — `enrichment/ids.py`,
  `enrichment/models.py`, `enrichment/outbox.py`, `enrichment/persistence.py`, `enrichment/services.py`,
  `enrichment/metrics.py`, and `migrations/versions/0002_persisted_trade_enrichment.py`.

Out:
- A real Temporal server / worker deployment for the *hand-rolled-vs-Temporal comparison* itself —
  `temporal_workflow.py`'s workflow/activity code is unit- and workflow-tested via the
  `temporalio.testing` time-skipping test environment, not a live cluster (see Testing plan). The
  durable per-trade path below *is* exercised against a real Temporal dev server + real Postgres in
  Docker, since that's the whole point of that half of this feature.

## Durable per-trade enrichment (the live path)

`GET /trades` (`api/routes_trades.py`) never calls Temporal or an enrichment service itself — it only
reads whatever the Temporal worker already persisted. Getting a result there durably, without ever
losing a workflow start, is a transactional outbox:

```
Kafka trade
  -> Redis deduplication
  -> one PostgreSQL transaction (consumer/postgres_sink.write_trade)
       -> insert trade
       -> if enrichment_enabled: set enrichment_status=pending, insert pending trade_enrichment_jobs row
  -> commit Kafka offset

Temporal worker (enrichment/worker.py)
  -> outbox dispatcher (enrichment/outbox.py) polls pending trade_enrichment_jobs rows
  -> starts one deterministic-ID EnrichmentWorkflow per row (enrichment/ids.py)
  -> marks the row dispatched

EnrichmentWorkflow (enrichment/temporal_workflow.py)
  -> runs risk_score + sentiment activities concurrently (enrichment/services.py)
  -> retains partial successes and typed error names on failure
  -> calls persist_trade_enrichment (enrichment/persistence.py)
       -> updates the exact trade row's enrichment/enrichment_status
       -> marks its outbox job completed

GET /trades -> reads enrichment/enrichment_status from PostgreSQL only
```

Key points:
- **Transactional outbox, not a direct Temporal call from the consumer**: the trade insert and its
  pending job insert commit together in one DB transaction (`postgres_sink.write_trade`) — a crash
  right after that commit can never lose the workflow start, since the pending row is still there for
  the next outbox poll.
- **Deterministic workflow IDs** (SHA-256 of `broker_id`/`trade_id`/`timestamp`, `enrichment/ids.py`)
  make re-dispatch idempotent: a duplicate `start_workflow` call raises
  `WorkflowAlreadyStartedError`, treated as success.
- **`disabled` is API-only** — the stored `enrichment_status` column only ever holds
  `not_requested`/`pending`/`completed`/`completed_with_errors`; `routes_trades.py` overrides the
  *response* to `null`/`"disabled"` while the flag is off, without touching the stored row (see
  `docs/features/feature-flags.md`). No backfill for trades ingested while the flag was off.
- **Real vs. demo services** (`enrichment/services.py`): an HTTP POST to
  `ENRICHMENT_RISK_SCORE_URL`/`ENRICHMENT_SENTIMENT_URL` if configured, else a deterministic
  (SHA-256-seeded, varies per trade) demo handler. HTTP 4xx is non-retryable; timeouts, network
  errors, and 5xx are retryable — same `RetryPolicy` as the hand-rolled-comparison workflow above.
- **Observability** (`enrichment/metrics.py`): the Temporal worker exposes its own `/metrics`
  (`enrichment_jobs_dispatched_total`, `enrichment_jobs_completed_total{status}`,
  `enrichment_job_latency_seconds`), same pattern as the consumer's `observability/metrics.py`.
- **Load characteristics observed against a real Docker stack**: a one-shot burst of ~1000 trades
  with the flag on drains slowly against the single-node `temporal:latest` dev server (`server
  start-dev`, sqlite-backed) and its default worker concurrency — expected for a demo-scale
  deployment, not a defect. The outbox dispatcher's `run()` loop does recover cleanly from the
  transient `CancelledError`/`RPCError` blips this produces (see the try/except around
  `dispatch_once()`), confirmed live rather than only in unit tests.
- The hand-rolled fan-out (`hand_rolled.py`) is unchanged and still tested, just no longer reachable
  from the live route — it remains the "how would you build this without a framework" answer.

## Design

- **Why both exist**: see `../ARCHITECTURE.md` ("Where Temporal fits") — Temporal is not a replacement
  for every async call, it's the right tool specifically for a *bounded, multi-step call with
  retries/timeouts that benefits from durable state*. The hand-rolled version stays in the codebase
  deliberately as the "how would you build this without a framework" interview answer per the plan's
  Week 8 mock-interview bar ("Build retry + timeout + circuit breaker from memory").
- Circuit breaker state machine matches the plan's own reference implementation exactly
  (`failure_threshold=3`, `recovery_timeout` configurable, `HALF_OPEN` allows exactly one probe).
- Hand-rolled retry uses `tenacity`'s `retry_if_exception_type` scoped to timeout-shaped exceptions
  only — matching the plan's explicit callout that retrying a "bad request" class of error is wrong.
- Temporal `RetryPolicy` uses `non_retryable_error_types` for the equivalent non-retryable case, so
  the two implementations make the same retry/no-retry decision for the same failure classes even
  though the mechanism differs.
- Both implementations return the same shape: a dict keyed by service name, each value either the
  enrichment payload or `{"data": None, "error": "<ExceptionType>"}` — so a caller could swap one for
  the other without changing how results are consumed.

## Python version notes

`hand_rolled.py` uses `asyncio.gather(return_exceptions=True)`, not `TaskGroup`, as its orchestration
primitive — `TaskGroup`'s all-or-nothing sibling-cancellation semantics are the wrong tool for "return
partial results per service," which is exactly the plan's own Week 4 model answer reasoning (see the
source HTML's "Full production pattern" code block, which also picks `gather()` over `TaskGroup` for
this reason). The `TaskGroup`-vs-`gather()` comparison itself already lives in
`common/version_compat_demo.py` — not duplicated here. No 3.12+/3.14-only syntax used in this feature;
checked against `../PYTHON_VERSION_NOTES.md`.

## Testing plan

- `circuit_breaker.py`: state-transition tests (closed → open after threshold failures → half-open
  after recovery timeout → closed on successful probe, or back to open on failed probe). Short
  `recovery_timeout` values (e.g. 0.05s) keep tests fast without mocking the clock.
- `hand_rolled.py`: tests against the fake mock services — all succeed, one times out and retries then
  succeeds, one exhausts retries and degrades gracefully, one non-timeout error is *not* retried, and
  a service whose circuit is already open is rejected immediately without a network-shaped call.
- `temporal_workflow.py`: activities are plain `async def` functions under `@activity.defn`, unit
  tested directly with zero Temporal runtime (`tests/enrichment/test_temporal_activities.py`). The
  workflow itself runs end to end against `temporalio.testing.WorkflowEnvironment`'s time-skipping
  test server (`tests/enrichment/test_temporal_workflow.py`) — confirmed working in this environment
  (the server binary downloads once from `temporal.download` and runs in-process, no Docker/real
  cluster needed). Session-scoped environment fixture, fresh `Worker` + unique task queue per test for
  isolation without repeated startup cost. One test in this file (`test_workflow_with_payload_...`)
  also seeds a real Postgres row via `pg_async_engine` and asserts the persisted result — proving the
  persist-once-at-the-end-of-the-workflow behavior, not just the fan-out.
- `outbox.py` (`tests/enrichment/test_outbox.py`): dispatch against real Postgres with a fake Temporal
  client — starts exactly one workflow per pending row, treats `WorkflowAlreadyStartedError` as
  success, marks rows dispatched, and (for the `run()` poll loop itself) stops promptly on `stop()`
  and survives a simulated transient DB failure without crashing.
- `persistence.py` (`tests/enrichment/test_persistence.py`): updates only the matching trade,
  preserves partial results, sets the correct final status, marks the matching job completed, and
  records the completion metric/latency.
- 31 enrichment tests total. 137/137 tests passing project-wide, ruff clean (verified against a live
  Docker stack — Postgres, Redis, Kafka, Temporal — not just mocked services).
