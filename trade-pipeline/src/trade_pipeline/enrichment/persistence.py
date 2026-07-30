"""Persistence activity — the only place enrichment results get written to
Postgres. Runs inside the Temporal worker (see worker.py), never on the API
request path (api/routes_trades.py only ever reads what's already stored
here).

Class-based, not a free function like ``call_enrichment_service`` — same
reasoning as ``RefreshTokenActivities`` in ``api/auth/refresh_workflow.py``:
it needs a real async session factory (a Postgres connection) injected at
worker startup, so one instance is constructed once and its bound method
registered with the Worker.
"""

from datetime import UTC, datetime

import structlog
from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker
from temporalio import activity

from trade_pipeline.common.db_models import Trade, TradeEnrichmentJob
from trade_pipeline.enrichment import metrics
from trade_pipeline.enrichment.models import PersistEnrichmentInput

logger = structlog.get_logger()


class EnrichmentPersistenceActivities:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    @activity.defn
    async def persist_trade_enrichment(self, input: PersistEnrichmentInput) -> None:
        enrichment = {
            name: {"data": result.data, "error": result.error}
            for name, result in input.results.items()
        }
        # completed_with_errors, not a bare failure — partial results from
        # sibling services that *did* succeed are still worth persisting and
        # surfacing (see docs/features/async-enrichment.md's example result).
        status = (
            "completed"
            if all(result.error is None for result in input.results.values())
            else "completed_with_errors"
        )

        async with self._session_factory() as session:
            # Read the job's created_at before updating it, purely to derive
            # the pending→persisted latency below — without this, "why
            # hasn't this trade's enrichment shown up yet" has no numeric
            # answer short of reading logs by hand.
            job = await session.get(TradeEnrichmentJob, input.workflow_id)

            await session.execute(
                update(Trade)
                .where(
                    Trade.broker_id == input.broker_id,
                    Trade.trade_id == input.trade_id,
                    Trade.timestamp == datetime.fromisoformat(input.timestamp),
                )
                .values(enrichment=enrichment, enrichment_status=status)
            )
            await session.execute(
                update(TradeEnrichmentJob)
                .where(TradeEnrichmentJob.workflow_id == input.workflow_id)
                .values(status="completed")
            )
            await session.commit()

        latency_seconds = (
            (datetime.now(UTC) - job.created_at).total_seconds() if job is not None else None
        )
        if latency_seconds is not None:
            metrics.record_completion(status=status, latency_seconds=latency_seconds)
        logger.info(
            "enrichment_persisted",
            workflow_id=input.workflow_id,
            broker_id=input.broker_id,
            trade_id=input.trade_id,
            status=status,
            latency_seconds=latency_seconds,
        )
