"""Transactional-outbox dispatcher for the per-trade enrichment workflow.

The consumer commits a trade and its pending ``trade_enrichment_jobs`` row in
one DB transaction (consumer/postgres_sink.write_trade) — so once that
commit succeeds, the workflow start can never be silently lost, even if the
process crashes immediately after. This dispatcher just polls for rows still
``pending`` and starts one deterministic-ID workflow per row (see
enrichment/ids.py), then marks the row ``dispatched``.

Runs alongside the Temporal worker (see worker.py), not as its own service —
one process, two concurrent loops (``Worker.run()`` and
``OutboxDispatcher.run()``).
"""

import asyncio
import contextlib
from datetime import UTC, datetime

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker
from temporalio.client import Client
from temporalio.exceptions import WorkflowAlreadyStartedError

from trade_pipeline.common.db_models import TradeEnrichmentJob
from trade_pipeline.enrichment import metrics
from trade_pipeline.enrichment.models import EnrichmentWorkflowInput, TradeEnrichmentPayload
from trade_pipeline.enrichment.temporal_workflow import EnrichmentWorkflow

logger = structlog.get_logger()


class OutboxDispatcher:
    def __init__(
        self,
        session_factory: async_sessionmaker,
        temporal_client: Client,
        task_queue: str,
        poll_interval_seconds: float = 0.5,
    ) -> None:
        self._session_factory = session_factory
        self._client = temporal_client
        self._task_queue = task_queue
        self._poll_interval_seconds = poll_interval_seconds
        self._stop_event = asyncio.Event()

    def stop(self) -> None:
        self._stop_event.set()

    async def run(self) -> None:
        """Poll until ``stop()`` is called. Uses ``wait_for`` on the stop
        event (not a plain ``sleep``) so ``stop()`` interrupts the wait
        immediately instead of waiting out the remainder of the interval.

        A single failed poll (e.g. a transient DB blip) must not kill this
        loop for the process's entire remaining lifetime — outbox rows are
        already durably committed by the consumer, so the only cost of a
        skipped poll is a delayed dispatch, not a lost one. The next
        iteration tries again after the usual poll interval, which already
        acts as a simple backoff.
        """
        while not self._stop_event.is_set():
            try:
                await self.dispatch_once()
            except Exception:
                logger.exception("outbox_dispatch_failed")
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._stop_event.wait(), timeout=self._poll_interval_seconds)

    async def dispatch_once(self) -> int:
        """Dispatch every currently-pending job. Returns how many it found —
        tests call this directly instead of driving the poll loop.
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(TradeEnrichmentJob).where(TradeEnrichmentJob.status == "pending")
            )
            jobs = list(result.scalars().all())

            for job in jobs:
                payload = TradeEnrichmentPayload(**job.payload)
                # Idempotent dispatch — a WorkflowAlreadyStartedError means
                # the workflow already exists for this deterministic ID
                # (e.g. a previous crash between start_workflow succeeding
                # and this row being marked dispatched). The job row still
                # needs to move to "dispatched" below either way.
                with contextlib.suppress(WorkflowAlreadyStartedError):
                    await self._client.start_workflow(
                        EnrichmentWorkflow.run,
                        EnrichmentWorkflowInput(
                            service_names=payload.service_names, payload=payload
                        ),
                        id=job.workflow_id,
                        task_queue=self._task_queue,
                    )

                await session.execute(
                    update(TradeEnrichmentJob)
                    .where(TradeEnrichmentJob.workflow_id == job.workflow_id)
                    .values(status="dispatched", dispatched_at=datetime.now(UTC))
                )
                metrics.record_dispatch()
                logger.info(
                    "outbox_job_dispatched",
                    workflow_id=job.workflow_id,
                    broker_id=job.broker_id,
                    trade_id=job.trade_id,
                )

            await session.commit()
            return len(jobs)
