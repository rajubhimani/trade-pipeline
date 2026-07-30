"""The same enrichment fan-out as a Temporal Workflow + Activities.

Compare against hand_rolled.py — same problem (call services in parallel,
retry timeouts only, degrade gracefully on failure), different mechanism.
See docs/features/async-enrichment.md and docs/ARCHITECTURE.md for why both
exist in this codebase rather than picking one.

Two ways to drive this workflow:

- Bare service names, no trade payload (``EnrichmentWorkflowInput(service_names=[...])``)
  — the original demo/test shape, still used by test_temporal_workflow.py.
  Activities run against the module-level test-script registry below and no
  persistence happens.
- A full ``TradeEnrichmentPayload`` — the real per-trade path, dispatched by
  the outbox (enrichment/outbox.py). Activities call the real/demo services
  in services.py, and the workflow persists the result back to the exact
  trade via ``EnrichmentPersistenceActivities`` (persistence.py) before
  returning.

Activities are plain ``async def``/bound-method functions under
``@activity.defn`` — they can be called directly in tests without any
Temporal runtime (see tests/enrichment/test_temporal_activities.py). The
workflow itself needs a Temporal environment (real or the
``temporalio.testing`` time-skipping test server) to execute, since
``workflow.execute_activity`` only works inside a running workflow.
"""

from datetime import timedelta

from temporalio import activity, workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError

with workflow.unsafe.imports_passed_through():
    from trade_pipeline.enrichment.mock_services import (
        EnrichmentBadRequestError,
        MockServiceScript,
    )
    from trade_pipeline.enrichment.models import (
        EnrichmentActivityResult,
        EnrichmentWorkflowInput,
        PersistEnrichmentInput,
        TradeEnrichmentPayload,
    )
    from trade_pipeline.enrichment.persistence import EnrichmentPersistenceActivities
    from trade_pipeline.enrichment.services import call_service

# Module-level registry so activities (which Temporal requires to be
# free functions, not closures) can look up which script to run by name.
# Only used by the test/demo scripts below — the real per-trade path calls
# services.call_service instead (see call_enrichment_service).
_SERVICE_SCRIPTS: dict[str, MockServiceScript] = {}

# Configured (or None, meaning "use the deterministic demo handler") URL per
# service name — populated at worker startup from EnrichmentSettings, same
# registry pattern as _SERVICE_SCRIPTS above. See worker.py.
_SERVICE_URLS: dict[str, str | None] = {}


def register_service_script(name: str, script: MockServiceScript) -> None:
    _SERVICE_SCRIPTS[name] = script


def register_service_url(name: str, url: str | None) -> None:
    _SERVICE_URLS[name] = url


@activity.defn
async def call_enrichment_service(
    service_name: str, payload: TradeEnrichmentPayload | None = None
) -> EnrichmentActivityResult:
    if payload is None:
        script = _SERVICE_SCRIPTS[service_name]
        try:
            data = await script.run()
        except EnrichmentBadRequestError as exc:
            # Non-retryable — surfaced as an ApplicationError with
            # non_retryable=True so Temporal's RetryPolicy stops immediately
            # instead of burning through retry attempts on a permanent failure.
            raise ApplicationError(str(exc), non_retryable=True) from exc
        return EnrichmentActivityResult(data=data, error=None)

    url = _SERVICE_URLS.get(service_name)
    try:
        data = await call_service(service_name, payload, url)
    except EnrichmentBadRequestError as exc:
        raise ApplicationError(str(exc), non_retryable=True) from exc
    return EnrichmentActivityResult(data=data, error=None)


@workflow.defn
class EnrichmentWorkflow:
    @workflow.run
    async def run(self, input: EnrichmentWorkflowInput) -> dict[str, EnrichmentActivityResult]:
        retry_policy = RetryPolicy(
            initial_interval=timedelta(milliseconds=10),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(milliseconds=50),
            maximum_attempts=3,
            non_retryable_error_types=[EnrichmentBadRequestError.__name__],
        )

        results: dict[str, EnrichmentActivityResult] = {}
        args_by_name = {
            name: (name,) if input.payload is None else (name, input.payload)
            for name in input.service_names
        }
        handles = {
            name: workflow.start_activity(
                call_enrichment_service,
                args=args,
                start_to_close_timeout=timedelta(seconds=2),
                retry_policy=retry_policy,
            )
            for name, args in args_by_name.items()
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

        if input.payload is not None:
            await workflow.execute_activity_method(
                EnrichmentPersistenceActivities.persist_trade_enrichment,
                PersistEnrichmentInput(
                    workflow_id=workflow.info().workflow_id,
                    broker_id=input.payload.broker_id,
                    trade_id=input.payload.trade_id,
                    timestamp=input.payload.timestamp,
                    results=results,
                ),
                start_to_close_timeout=timedelta(seconds=5),
                retry_policy=RetryPolicy(maximum_attempts=5),
            )

        return results
