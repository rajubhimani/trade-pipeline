"""Temporal worker process — the deployed counterpart to the two worked
Temporal examples in this codebase (``temporal_workflow.py``'s
``EnrichmentWorkflow``, ``api/auth/refresh_workflow.py``'s
``RefreshTokenRotationWorkflow``). Both register on one task queue: a
Temporal ``Worker`` binds to exactly one task queue, and there's no reason
to run two processes for two low-volume demo workflows.

The enrichment activity's mock services are registered with the same names
api/main.py wires up for the hand-rolled path ("risk_score", "sentiment") —
this worker is the same problem solved a different way, not an isolated
demo, so it should be comparable against the hand-rolled path 1:1.
"""

import asyncio

from redis import Redis
from temporalio.client import Client
from temporalio.worker import Worker

from trade_pipeline.api.auth.refresh_tokens import RefreshTokenStore
from trade_pipeline.api.auth.refresh_workflow import (
    RefreshTokenActivities,
    RefreshTokenRotationWorkflow,
)
from trade_pipeline.common.config import load_config
from trade_pipeline.enrichment.mock_services import always_succeeds
from trade_pipeline.enrichment.temporal_workflow import (
    EnrichmentWorkflow,
    call_enrichment_service,
    register_service_script,
)


def _register_enrichment_scripts() -> None:
    register_service_script("risk_score", always_succeeds({"score": 42}))
    register_service_script("sentiment", always_succeeds({"index": "neutral"}))


async def main() -> None:
    config = load_config()
    _register_enrichment_scripts()

    client = await Client.connect(config.temporal.address)
    redis_client = Redis.from_url(config.redis.url)
    refresh_activities = RefreshTokenActivities(RefreshTokenStore(redis=redis_client))

    worker = Worker(
        client,
        task_queue=config.temporal.task_queue,
        workflows=[EnrichmentWorkflow, RefreshTokenRotationWorkflow],
        activities=[call_enrichment_service, refresh_activities.rotate],
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
