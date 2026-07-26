# Feature: Async enrichment — hand-rolled vs Temporal workflow

Status: shipped
Task: docs/tasks/completed/T-6-async-enrichment.md

## Problem / motivation

Component 4 of the project (`../ARCHITECTURE.md`) — the query API calls out to 3 mock enrichment
services in parallel to attach extra data to a trade before returning it. This is also where the
plan's Week 4 async-mastery track becomes real code: `gather()` vs `wait()` vs `TaskGroup`, timeout vs
backoff, and a hand-rolled circuit breaker are all named explicitly as "what Q3 wanted" in the source
plan (`../../faang_python_full_prep.html`).

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
- `enrichment/temporal_workflow.py` — the same fan-out as a Temporal `@workflow.defn` calling 3
  `@activity.defn` activities concurrently, with a `RetryPolicy` per activity matching the hand-rolled
  version's retry semantics (retry on timeout-shaped errors, not on non-retryable ones), and partial
  results on activity failure instead of failing the whole workflow.

Out:
- Wiring enrichment into the live `GET /trades` endpoint (T-5) — this feature ships the two
  orchestration implementations and their tests; integrating either into the API route is tracked
  separately if picked up later, to keep this feature's scope to the orchestration comparison itself.
- A real Temporal server / worker deployment — Temporal's workflow code is tested via the
  `temporalio.testing` time-skipping test environment, not a live cluster (see Testing plan).

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
  tested directly with zero Temporal runtime (`tests/enrichment/test_temporal_activities.py`, 2 tests).
  The workflow itself runs end to end against `temporalio.testing.WorkflowEnvironment`'s time-skipping
  test server (`tests/enrichment/test_temporal_workflow.py`, 3 tests) — confirmed working in this
  environment (the server binary downloads once from `temporal.download` and runs in-process, no
  Docker/real cluster needed). Session-scoped environment fixture, fresh `Worker` + unique task queue
  per test for isolation without repeated startup cost.
- 17 enrichment tests total (6 circuit breaker, 6 hand-rolled orchestration, 2 Temporal activity, 3
  Temporal workflow). 53/53 tests passing project-wide, ruff clean.
