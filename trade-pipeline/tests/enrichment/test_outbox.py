"""Outbox dispatcher tests against real Postgres — a fake Temporal client
stands in for the real one so these stay fast unit tests of the dispatch
logic itself (poll pending, start exactly one workflow per row, treat
``WorkflowAlreadyStartedError`` as success, mark dispatched) without needing
a live Temporal server. End-to-end workflow execution is covered by
test_temporal_workflow.py.
"""

import asyncio
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from temporalio.exceptions import WorkflowAlreadyStartedError

from trade_pipeline.common.db_models import TradeEnrichmentJob
from trade_pipeline.enrichment.ids import compute_workflow_id
from trade_pipeline.enrichment.outbox import OutboxDispatcher


class _FakeTemporalClient:
    def __init__(self, already_started: set[str] | None = None) -> None:
        self.started_ids: list[str] = []
        self._already_started = already_started or set()

    async def start_workflow(self, workflow, arg, *, id, task_queue):
        if id in self._already_started:
            raise WorkflowAlreadyStartedError(id, "EnrichmentWorkflow")
        self.started_ids.append(id)


def _job_payload(**overrides) -> dict:
    defaults = {
        "broker_id": "broker-1",
        "trade_id": "t-1",
        "timestamp": "2026-07-26T00:00:00+00:00",
        "symbol": "AAPL",
        "qty": 10,
        "price": "190.50",
        "service_names": ["risk_score", "sentiment"],
    }
    defaults.update(overrides)
    return defaults


async def _insert_job(session_factory, *, workflow_id: str, status: str = "pending", **overrides):
    payload = _job_payload(**overrides)
    async with session_factory() as session:
        session.add(
            TradeEnrichmentJob(
                workflow_id=workflow_id,
                broker_id=payload["broker_id"],
                trade_id=payload["trade_id"],
                trade_timestamp=datetime.fromisoformat(payload["timestamp"]),
                payload=payload,
                status=status,
            )
        )
        await session.commit()


async def test_dispatch_once_starts_workflow_and_marks_dispatched(pg_async_engine):
    session_factory = async_sessionmaker(bind=pg_async_engine, expire_on_commit=False)
    workflow_id = compute_workflow_id("broker-1", "t-1", datetime(2026, 7, 26, tzinfo=UTC))
    await _insert_job(session_factory, workflow_id=workflow_id)

    client = _FakeTemporalClient()
    dispatcher = OutboxDispatcher(session_factory, client, task_queue="test-queue")

    dispatched_count = await dispatcher.dispatch_once()

    assert dispatched_count == 1
    assert client.started_ids == [workflow_id]

    async with session_factory() as session:
        job = (
            await session.execute(
                select(TradeEnrichmentJob).where(TradeEnrichmentJob.workflow_id == workflow_id)
            )
        ).scalar_one()
    assert job.status == "dispatched"
    assert job.dispatched_at is not None


async def test_dispatch_once_ignores_non_pending_jobs(pg_async_engine):
    session_factory = async_sessionmaker(bind=pg_async_engine, expire_on_commit=False)
    await _insert_job(session_factory, workflow_id="wf-already-dispatched", status="dispatched")

    client = _FakeTemporalClient()
    dispatcher = OutboxDispatcher(session_factory, client, task_queue="test-queue")

    dispatched_count = await dispatcher.dispatch_once()

    assert dispatched_count == 0
    assert client.started_ids == []


async def test_dispatch_once_treats_already_started_workflow_as_idempotent(pg_async_engine):
    """A crash between start_workflow succeeding and this row being marked
    dispatched would otherwise re-attempt the same deterministic workflow ID
    on the next poll — that must succeed (job still moves to "dispatched"),
    not raise.
    """
    session_factory = async_sessionmaker(bind=pg_async_engine, expire_on_commit=False)
    workflow_id = "wf-dup"
    await _insert_job(session_factory, workflow_id=workflow_id)

    client = _FakeTemporalClient(already_started={workflow_id})
    dispatcher = OutboxDispatcher(session_factory, client, task_queue="test-queue")

    dispatched_count = await dispatcher.dispatch_once()

    assert dispatched_count == 1
    async with session_factory() as session:
        job = (
            await session.execute(
                select(TradeEnrichmentJob).where(TradeEnrichmentJob.workflow_id == workflow_id)
            )
        ).scalar_one()
    assert job.status == "dispatched"


async def test_dispatch_once_dispatches_multiple_pending_jobs(pg_async_engine):
    session_factory = async_sessionmaker(bind=pg_async_engine, expire_on_commit=False)
    await _insert_job(session_factory, workflow_id="wf-1", trade_id="t-1")
    await _insert_job(session_factory, workflow_id="wf-2", trade_id="t-2")

    client = _FakeTemporalClient()
    dispatcher = OutboxDispatcher(session_factory, client, task_queue="test-queue")

    dispatched_count = await dispatcher.dispatch_once()

    assert dispatched_count == 2
    assert set(client.started_ids) == {"wf-1", "wf-2"}


async def test_run_dispatches_pending_jobs_until_stopped(pg_async_engine):
    session_factory = async_sessionmaker(bind=pg_async_engine, expire_on_commit=False)
    workflow_id = "wf-run-loop"
    await _insert_job(session_factory, workflow_id=workflow_id)

    client = _FakeTemporalClient()
    dispatcher = OutboxDispatcher(
        session_factory, client, task_queue="test-queue", poll_interval_seconds=0.05
    )

    task = asyncio.create_task(dispatcher.run())
    try:
        await asyncio.sleep(0.2)  # let at least one poll happen
    finally:
        dispatcher.stop()
        await asyncio.wait_for(task, timeout=1)

    assert client.started_ids == [workflow_id]
    async with session_factory() as session:
        job = (
            await session.execute(
                select(TradeEnrichmentJob).where(TradeEnrichmentJob.workflow_id == workflow_id)
            )
        ).scalar_one()
    assert job.status == "dispatched"


async def test_stop_interrupts_the_poll_wait_immediately(pg_async_engine):
    """A long poll interval must not delay shutdown — stop() interrupts the
    wait via the shared asyncio.Event, it doesn't wait out the interval.
    """
    session_factory = async_sessionmaker(bind=pg_async_engine, expire_on_commit=False)
    client = _FakeTemporalClient()
    dispatcher = OutboxDispatcher(
        session_factory, client, task_queue="test-queue", poll_interval_seconds=10
    )

    task = asyncio.create_task(dispatcher.run())
    await asyncio.sleep(0.05)  # let it complete its first poll and enter the wait
    dispatcher.stop()

    # Would take ~10s if stop() didn't interrupt the wait early.
    await asyncio.wait_for(task, timeout=1)


class _FlakySessionFactory:
    """Wraps a real session factory, raising for the first N calls — stands
    in for a transient DB blip so run()'s error handling can be tested
    without actually breaking a real connection.
    """

    def __init__(self, real_factory, fail_times: int) -> None:
        self._real_factory = real_factory
        self._remaining_failures = fail_times

    def __call__(self):
        if self._remaining_failures > 0:
            self._remaining_failures -= 1
            raise RuntimeError("simulated transient DB failure")
        return self._real_factory()


async def test_run_survives_a_transient_poll_failure(pg_async_engine):
    session_factory = async_sessionmaker(bind=pg_async_engine, expire_on_commit=False)
    workflow_id = "wf-survives-failure"
    await _insert_job(session_factory, workflow_id=workflow_id)

    flaky_factory = _FlakySessionFactory(session_factory, fail_times=1)
    client = _FakeTemporalClient()
    dispatcher = OutboxDispatcher(
        flaky_factory, client, task_queue="test-queue", poll_interval_seconds=0.05
    )

    task = asyncio.create_task(dispatcher.run())
    try:
        await asyncio.sleep(0.3)  # one failed poll, then a successful one
    finally:
        dispatcher.stop()
        await asyncio.wait_for(task, timeout=1)

    assert client.started_ids == [workflow_id]
