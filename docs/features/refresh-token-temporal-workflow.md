# Feature: Refresh-token rotation as a Temporal workflow

Status: shipped
Task: docs/tasks/completed/T-12-refresh-token-temporal-workflow.md

## Problem / motivation

Mentioned as a candidate in `docs/ARCHITECTURE.md`; not required for the auth flow to work (the direct
synchronous path in `api/routes_auth.py` already works and stays production), but wanted as a second,
deliberately different Temporal example beyond `enrichment/temporal_workflow.py`'s parallel fan-out —
useful for comparing two distinct Temporal usage patterns side by side.

## Scope

In: `api/auth/refresh_workflow.py` — `RefreshTokenRotationWorkflow` (single activity, not a fan-out)
wrapping the existing `RefreshTokenStore.rotate()` (Redis GETDEL + re-issue). `RefreshTokenActivities`
is a class holding one `RefreshTokenStore` instance (constructed once per worker), with `rotate`
registered as a bound-method activity — the officially supported temporalio pattern for activities
needing an injected dependency, as opposed to `temporal_workflow.py`'s module-level script registry
(which exists to swap in different *test* scripts, a different need).

Out:
- Wiring this into the live `/auth/refresh` endpoint. A single Redis round trip has no need for
  Temporal's durability guarantees, and adding a workflow-engine hop to every token refresh would only
  add latency and a new availability dependency for no real benefit — same reasoning
  `async-enrichment.md` gives for keeping the hand-rolled and Temporal enrichment paths side by side
  rather than replacing one with the other.
- A persistent, signal-driven "session" workflow (one long-running workflow instance per login,
  receiving refresh signals over its lifetime) — a more elaborate, genuinely different Temporal
  pattern that would be worth exploring separately, but out of proportion for this task's stated scope
  ("a good second Temporal example", low priority).

## Design

- **Class-based activity, not a free function**: `RefreshTokenActivities.__init__` takes the
  `RefreshTokenStore` (backed by a real `Redis` connection); the *bound* `rotate` method is registered
  with the `Worker` (`activities=[activities.rotate]`), matching the pattern `workflow.execute_activity_method`
  is built for.
- **Non-retryable `ApplicationError` for a bad token**: mirrors `temporal_workflow.py`'s
  `call_enrichment_service` — an unknown/already-consumed token can never succeed on retry, so the
  activity raises `ApplicationError(..., non_retryable=True)` rather than letting Temporal's default
  retry policy burn through attempts on a permanent failure.
- **Bug caught during verification**: the workflow's `run()` originally caught the activity's
  `ActivityError` and re-raised a plain `RefreshTokenError` to give callers a Temporal-independent
  exception type. This hung every failing-path test indefinitely — raising an arbitrary non-Temporal
  exception directly from workflow code isn't treated as a workflow *execution* failure but as a
  workflow *task* failure, which the SDK retries forever rather than ever completing the workflow. Fixed
  by letting the activity's failure propagate as-is (the SDK wraps it in `ActivityError` /
  `WorkflowFailureError` correctly on its own) — `ApplicationError`, raised inside the activity, is the
  SDK-recognized way to fail a workflow deterministically; a workflow's own code should not re-raise
  plain domain exceptions to change the exception type callers see.

## Testing plan

- `tests/api/auth/test_refresh_workflow_activities.py`: activity-level tests calling `rotate()`
  directly against a real `redis_client` fixture — no Temporal runtime needed (`@activity.defn` only
  changes registration).
- `tests/api/auth/test_refresh_workflow.py`: full workflow tests against Temporal's time-skipping test
  server (same approach as `test_temporal_workflow.py`) — one confirms a valid token rotates and the
  old token becomes unusable, one confirms an invalid token fails the workflow (`WorkflowFailureError`)
  without hanging.
