"""The same enrichment fan-out as a Temporal Workflow + Activities.

Compare against hand_rolled.py — same problem (call 3 services in parallel,
retry timeouts only, degrade gracefully on failure), different mechanism.
See docs/features/async-enrichment.md and docs/ARCHITECTURE.md for why both
exist in this codebase rather than picking one.

Activities are plain ``async def`` functions under ``@activity.defn`` — they
can be called directly in tests without any Temporal runtime, same as any
other async function (see tests/enrichment/test_temporal_activities.py).
The workflow itself needs a Temporal environment (real or the
``temporalio.testing`` time-skipping test server) to execute, since
``workflow.execute_activity`` only works inside a running workflow.
"""

from dataclasses import dataclass
from datetime import timedelta

from temporalio import activity, workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError

with workflow.unsafe.imports_passed_through():
    from trade_pipeline.enrichment.mock_services import (
        EnrichmentBadRequestError,
        MockServiceScript,
    )

# Module-level registry so activities (which Temporal requires to be
# free functions, not closures) can look up which script to run by name.
# Only used by the test/demo scripts below — a real deployment would call an
# actual HTTP client here instead.
_SERVICE_SCRIPTS: dict[str, MockServiceScript] = {}


def register_service_script(name: str, script: MockServiceScript) -> None:
    _SERVICE_SCRIPTS[name] = script


@dataclass(frozen=True, slots=True)
class EnrichmentActivityResult:
    data: dict | None
    error: str | None


@activity.defn
async def call_enrichment_service(service_name: str) -> EnrichmentActivityResult:
    script = _SERVICE_SCRIPTS[service_name]
    try:
        data = await script.run()
    except EnrichmentBadRequestError as exc:
        # Non-retryable — surfaced as an ApplicationError with
        # non_retryable=True so Temporal's RetryPolicy stops immediately
        # instead of burning through retry attempts on a permanent failure.
        raise ApplicationError(str(exc), non_retryable=True) from exc
    return EnrichmentActivityResult(data=data, error=None)


@workflow.defn
class EnrichmentWorkflow:
    @workflow.run
    async def run(self, service_names: list[str]) -> dict[str, EnrichmentActivityResult]:
        retry_policy = RetryPolicy(
            initial_interval=timedelta(milliseconds=10),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(milliseconds=50),
            maximum_attempts=3,
            non_retryable_error_types=[EnrichmentBadRequestError.__name__],
        )

        results: dict[str, EnrichmentActivityResult] = {}
        handles = {
            name: workflow.start_activity(
                call_enrichment_service,
                name,
                start_to_close_timeout=timedelta(seconds=2),
                retry_policy=retry_policy,
            )
            for name in service_names
        }

        for name, handle in handles.items():
            try:
                results[name] = await handle
            except ActivityError as exc:
                # Graceful degradation, same contract as hand_rolled.enrich —
                # one service failing doesn't fail the whole workflow.
                cause = exc.cause
                error_name = type(cause).__name__ if cause else type(exc).__name__
                results[name] = EnrichmentActivityResult(data=None, error=error_name)

        return results
