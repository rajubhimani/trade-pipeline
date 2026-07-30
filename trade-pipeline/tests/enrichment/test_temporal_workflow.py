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
from datetime import UTC, datetime
from decimal import Decimal

import pytest_asyncio
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import async_sessionmaker
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from trade_pipeline.common.db_models import Trade
from trade_pipeline.enrichment.mock_services import (
    always_bad_request,
    always_succeeds,
    always_times_out,
)
from trade_pipeline.enrichment.models import EnrichmentWorkflowInput, TradeEnrichmentPayload
from trade_pipeline.enrichment.persistence import EnrichmentPersistenceActivities
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
            EnrichmentWorkflowInput(service_names=service_names),
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


async def test_workflow_with_payload_persists_result_to_the_exact_trade(env, pg_async_engine):
    """The real per-trade path (outbox.py's dispatch shape): a workflow
    given a ``TradeEnrichmentPayload`` runs both services (against the
    deterministic demo handler — no URL registered for either service name
    in this test) and persists once, degrading gracefully is covered above.
    """
    session_factory = async_sessionmaker(bind=pg_async_engine, expire_on_commit=False)
    timestamp = datetime(2026, 7, 26, tzinfo=UTC)
    async with session_factory() as session:
        await session.execute(
            insert(Trade).values(
                broker_id="broker-wf",
                trade_id="t-wf-1",
                symbol="AAPL",
                qty=5,
                price=Decimal("10.00"),
                timestamp=timestamp,
            )
        )
        await session.commit()

    payload = TradeEnrichmentPayload(
        broker_id="broker-wf",
        trade_id="t-wf-1",
        timestamp=timestamp.isoformat(),
        symbol="AAPL",
        qty=5,
        price="10.00",
        service_names=["risk_score", "sentiment"],
    )
    persistence_activities = EnrichmentPersistenceActivities(session_factory)

    # Not routed through _run_workflow — that helper always builds
    # EnrichmentWorkflowInput with no payload; this test needs the real
    # per-trade shape (payload set), so it drives the Worker/execute_workflow
    # call directly.
    task_queue = f"enrichment-{uuid.uuid4()}"
    async with Worker(
        env.client,
        task_queue=task_queue,
        workflows=[EnrichmentWorkflow],
        activities=[call_enrichment_service, persistence_activities.persist_trade_enrichment],
    ):
        result = await env.client.execute_workflow(
            EnrichmentWorkflow.run,
            EnrichmentWorkflowInput(service_names=payload.service_names, payload=payload),
            id=f"wf-{uuid.uuid4()}",
            task_queue=task_queue,
        )

    assert result["risk_score"].error is None
    assert result["sentiment"].error is None

    async with session_factory() as session:
        row = (
            await session.execute(
                select(Trade).where(Trade.broker_id == "broker-wf", Trade.trade_id == "t-wf-1")
            )
        ).scalar_one()

    assert row.enrichment_status == "completed"
    assert row.enrichment["risk_score"]["data"]["trade_id"] == "t-wf-1"
    assert row.enrichment["sentiment"]["data"]["trade_id"] == "t-wf-1"
