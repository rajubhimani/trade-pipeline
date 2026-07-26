# [done] Async enrichment — gather/TaskGroup + circuit breaker + Temporal workflow variant (component-4) — id: T-6

Added: 2026-07-26
Completed: 2026-07-26
Notes: Feature doc written first (docs/features/async-enrichment.md), per create-feature workflow.
Shipped both the hand-rolled orchestration (gather + wait_for + tenacity retry-on-timeout-only +
per-service circuit breaker) and a Temporal Workflow + Activities variant with an equivalent
RetryPolicy, so the same problem is solved two ways for comparison (see docs/ARCHITECTURE.md).
Verified via web research that temporalio's time-skipping test server (temporalio.testing.WorkflowEnvironment)
actually works in this environment before committing to full workflow-level tests rather than settling
for activity-only coverage.
Circuit breaker deviates from the plan's reference code on purpose: call() takes a zero-arg callable
instead of an already-created coroutine, to avoid a "coroutine was never awaited" RuntimeWarning when
the circuit is open (would fail the suite under this project's warnings-as-errors pytest config).
17 new tests (6 circuit breaker state-transition, 6 hand-rolled orchestration incl. graceful
degradation and open-circuit rejection, 2 Temporal activity unit tests, 3 Temporal workflow
integration tests against the real time-skipping test server). 53/53 tests passing project-wide, ruff
clean.
Feature doc: docs/features/async-enrichment.md
