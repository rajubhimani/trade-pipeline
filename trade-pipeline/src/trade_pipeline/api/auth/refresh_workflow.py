"""Refresh-token rotation as a Temporal workflow — a second, deliberately
different Temporal pattern from ``enrichment/temporal_workflow.py``'s
parallel fan-out: here it's a single side-effecting operation (Redis GETDEL
+ re-issue, see ``refresh_tokens.py``) wrapped for durable retry and
observability, not concurrency.

Not wired into the live ``/auth/refresh`` endpoint (see
``docs/DECISIONS.md``) — that stays a direct synchronous call, since a
single Redis round trip has no need for Temporal's durability guarantees
and adding a workflow-engine round trip to every token refresh would only
add latency and a new availability dependency for no real benefit. This
module exists as a second worked Temporal example for comparison/learning
(T-12), the same reasoning ``async-enrichment.md`` gives for keeping both
the hand-rolled and Temporal enrichment paths side by side.

``RefreshTokenActivities`` is a class, not a free function like
``call_enrichment_service`` — it needs a real ``RefreshTokenStore`` (and
therefore a Redis connection) injected at worker startup, so one instance
is constructed once and its bound method registered with the Worker; this
is temporalio's documented pattern for activities with shared dependencies,
as opposed to the module-level script registry ``temporal_workflow.py``
uses for swapping in different *test* scripts.
"""

from dataclasses import dataclass
from datetime import timedelta

from temporalio import activity, workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError

with workflow.unsafe.imports_passed_through():
    from trade_pipeline.api.auth.refresh_tokens import RefreshTokenError, RefreshTokenStore


@dataclass(frozen=True, slots=True)
class RotationResult:
    user_id: str
    new_token: str


class RefreshTokenActivities:
    def __init__(self, store: RefreshTokenStore) -> None:
        self._store = store

    @activity.defn
    async def rotate(self, token: str) -> RotationResult:
        try:
            user_id, new_token = self._store.rotate(token)
        except RefreshTokenError as exc:
            # Unknown/already-used token — retrying can never succeed, so
            # this must surface as non-retryable rather than burn through
            # the workflow's retry policy on a permanent failure.
            raise ApplicationError(str(exc), non_retryable=True) from exc
        return RotationResult(user_id=user_id, new_token=new_token)


@workflow.defn
class RefreshTokenRotationWorkflow:
    @workflow.run
    async def run(self, token: str) -> RotationResult:
        retry_policy = RetryPolicy(
            initial_interval=timedelta(milliseconds=50),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(seconds=1),
            maximum_attempts=3,
            non_retryable_error_types=[RefreshTokenError.__name__],
        )
        # Let a failed activity propagate as-is (wrapped in Temporal's own
        # ActivityError/WorkflowFailureError by the SDK) rather than
        # catching it here to re-raise a plain RefreshTokenError: raising an
        # arbitrary non-Temporal exception from workflow code isn't treated
        # as a workflow *execution* failure, but as a workflow *task*
        # failure — which the SDK retries indefinitely rather than ever
        # completing the workflow, silently hanging any caller awaiting the
        # result. `ApplicationError` (raised in the activity above) is the
        # SDK-recognized way to fail a workflow deterministically.
        return await workflow.execute_activity_method(
            RefreshTokenActivities.rotate,
            token,
            start_to_close_timeout=timedelta(seconds=2),
            retry_policy=retry_policy,
        )
