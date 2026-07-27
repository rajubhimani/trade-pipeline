"""End-to-end workflow tests against Temporal's time-skipping test server.

Confirmed working in this environment (the server binary downloads once from
temporal.download and runs locally, in-process, no Docker/real cluster
needed) — see docs/features/async-enrichment.md for the fallback plan if a
given environment can't reach that domain (activity-level tests in
test_temporal_activities.py still cover the business logic with zero network
dependency either way).

Session-scoped environment (one downloaded/started server for the whole test
session) with a fresh Worker + unique task queue per test to keep tests
isolated without paying the startup cost repeatedly.
"""

import uuid

import pytest_asyncio
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from trade_pipeline.enrichment.mock_services import (
    always_bad_request,
    always_succeeds,
    always_times_out,
)
from trade_pipeline.enrichment.temporal_workflow import (
    EnrichmentWorkflow,
    call_enrichment_service,
    register_service_script,
)


@pytest_asyncio.fixture(scope="session")
async def env():
    async with await WorkflowEnvironment.start_time_skipping() as environment:
        yield environment


async def _run_workflow(env: WorkflowEnvironment, service_names: list[str]) -> dict:
    task_queue = f"enrichment-{uuid.uuid4()}"
    async with Worker(
        env.client,
        task_queue=task_queue,
        workflows=[EnrichmentWorkflow],
        activities=[call_enrichment_service],
    ):
        return await env.client.execute_workflow(
            EnrichmentWorkflow.run,
            service_names,
            id=f"wf-{uuid.uuid4()}",
            task_queue=task_queue,
        )


async def test_workflow_returns_data_for_all_successful_services(env):
    register_service_script("wf-a", always_succeeds({"score": 1}))
    register_service_script("wf-b", always_succeeds({"score": 2}))

    result = await _run_workflow(env, ["wf-a", "wf-b"])

    assert result["wf-a"].data == {"score": 1}
    assert result["wf-b"].data == {"score": 2}


async def test_workflow_degrades_gracefully_on_one_failing_service(env):
    register_service_script("wf-good", always_succeeds({"score": 3}))
    register_service_script("wf-bad", always_bad_request())

    result = await _run_workflow(env, ["wf-good", "wf-bad"])

    assert result["wf-good"].data == {"score": 3}
    assert result["wf-bad"].data is None
    assert result["wf-bad"].error == "ApplicationError"


async def test_workflow_retries_timeout_then_gives_up_gracefully(env):
    # always_times_out never succeeds, so this exercises the retry policy
    # exhausting its attempts and the workflow still returning a partial
    # (degraded) result rather than raising out of the whole workflow.
    register_service_script("wf-timeout", always_times_out())

    result = await _run_workflow(env, ["wf-timeout"])

    assert result["wf-timeout"].data is None
    assert result["wf-timeout"].error is not None
