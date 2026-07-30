"""Temporal worker process — the deployed counterpart to the two worked
Temporal examples in this codebase (``temporal_workflow.py``'s
``EnrichmentWorkflow``, ``api/auth/refresh_workflow.py``'s
``RefreshTokenRotationWorkflow``). Both register on one task queue: a
Temporal ``Worker`` binds to exactly one task queue, and there's no reason
to run two processes for two low-volume demo workflows.

Also runs the transactional-outbox dispatcher (enrichment/outbox.py)
alongside the Worker, in the same process — it's what actually starts one
EnrichmentWorkflow per newly-ingested trade (see
consumer/postgres_sink.write_trade for the other half of the outbox).

The enrichment activity's real/demo service URLs (or lack thereof — falls
back to a deterministic demo handler, see enrichment/services.py) are
registered with the same names api/main.py's now-removed hand-rolled path
used ("risk_score", "sentiment") — this worker is the same problem solved a
different way, not an isolated demo, so it should be comparable against the
hand-rolled path 1:1.

Exposes its own ``/metrics`` (see enrichment/metrics.py) — same reasoning as
the consumer's (observability/metrics.py): a separate process with no
FastAPI app of its own to get request-latency instrumentation for free.
"""

import asyncio
import signal

from redis import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from temporalio.client import Client
from temporalio.worker import Worker

from trade_pipeline.api.auth.refresh_tokens import RefreshTokenStore
from trade_pipeline.api.auth.refresh_workflow import (
    RefreshTokenActivities,
    RefreshTokenRotationWorkflow,
)
from trade_pipeline.common.config import load_config
from trade_pipeline.enrichment import metrics
from trade_pipeline.enrichment.outbox import OutboxDispatcher
from trade_pipeline.enrichment.persistence import EnrichmentPersistenceActivities
from trade_pipeline.enrichment.temporal_workflow import (
    EnrichmentWorkflow,
    call_enrichment_service,
    register_service_url,
)

METRICS_PORT = 8002


def _register_enrichment_service_urls(config) -> None:
    register_service_url("risk_score", config.enrichment.risk_score_url)
    register_service_url("sentiment", config.enrichment.sentiment_url)


async def main() -> None:
    config = load_config()
    _register_enrichment_service_urls(config)
    metrics.start_metrics_server(port=METRICS_PORT)

    client = await Client.connect(config.temporal.address)
    redis_client = Redis.from_url(config.redis.url)
    refresh_activities = RefreshTokenActivities(RefreshTokenStore(redis=redis_client))

    # Wider pool than SQLAlchemy's default (5 + 10 overflow = 15): Temporal's
    # default max_concurrent_activities is ~100, and every
    # persist_trade_enrichment call needs its own connection — under a burst
    # of concurrent enrichment workflows, the default pool queues requests
    # past the activity's start_to_close_timeout, which Temporal then cancels
    # as a timed-out attempt (confirmed against a live 1000-trade burst).
    engine = create_async_engine(config.postgres.dsn, pool_size=20, max_overflow=30)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    persistence_activities = EnrichmentPersistenceActivities(session_factory)

    worker = Worker(
        client,
        task_queue=config.temporal.task_queue,
        workflows=[EnrichmentWorkflow, RefreshTokenRotationWorkflow],
        activities=[
            call_enrichment_service,
            refresh_activities.rotate,
            persistence_activities.persist_trade_enrichment,
        ],
    )
    dispatcher = OutboxDispatcher(
        session_factory=session_factory,
        temporal_client=client,
        task_queue=config.temporal.task_queue,
        poll_interval_seconds=config.temporal.outbox_poll_interval_seconds,
    )

    # SIGTERM handling (docker compose stop) needs a Unix event loop — this
    # process only ever runs in the temporal-worker container (see
    # Dockerfile.temporal / docker-compose.yml), never on a bare Windows dev
    # box, so add_signal_handler is always available where main() actually runs.
    loop = asyncio.get_running_loop()
    stop = loop.create_future()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set_result, None)

    async with worker:
        dispatcher_task = asyncio.create_task(dispatcher.run())
        try:
            await stop
        finally:
            dispatcher.stop()
            await dispatcher_task
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
