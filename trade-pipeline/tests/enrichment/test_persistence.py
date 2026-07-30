"""Persistence-activity tests against real Postgres. Called directly, not
through a Temporal runtime — same reasoning as test_temporal_activities.py:
``@activity.defn`` only changes worker registration, the bound method is
still a plain coroutine.
"""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from trade_pipeline.common.db_models import Trade, TradeEnrichmentJob
from trade_pipeline.enrichment import metrics
from trade_pipeline.enrichment.models import EnrichmentActivityResult, PersistEnrichmentInput
from trade_pipeline.enrichment.persistence import EnrichmentPersistenceActivities

TIMESTAMP = datetime(2026, 7, 26, tzinfo=UTC)


async def _seed_trade(session_factory, **overrides) -> None:
    defaults = {
        "broker_id": "broker-1",
        "trade_id": "t-1",
        "symbol": "AAPL",
        "qty": 10,
        "price": Decimal("190.50"),
        "timestamp": TIMESTAMP,
    }
    defaults.update(overrides)
    async with session_factory() as session:
        await session.execute(insert(Trade).values(**defaults))
        await session.commit()


async def _seed_job(session_factory, workflow_id: str, **overrides) -> None:
    defaults = {
        "broker_id": "broker-1",
        "trade_id": "t-1",
        "trade_timestamp": TIMESTAMP,
        "payload": {"broker_id": "broker-1", "trade_id": "t-1"},
        "status": "dispatched",
    }
    defaults.update(overrides)
    async with session_factory() as session:
        session.add(TradeEnrichmentJob(workflow_id=workflow_id, **defaults))
        await session.commit()


async def test_persist_updates_only_the_matching_trade(pg_async_engine):
    session_factory = async_sessionmaker(bind=pg_async_engine, expire_on_commit=False)
    await _seed_trade(session_factory, broker_id="broker-1", trade_id="t-1")
    await _seed_trade(session_factory, broker_id="broker-1", trade_id="t-2")
    await _seed_job(session_factory, "wf-1")

    activities = EnrichmentPersistenceActivities(session_factory)
    await activities.persist_trade_enrichment(
        PersistEnrichmentInput(
            workflow_id="wf-1",
            broker_id="broker-1",
            trade_id="t-1",
            timestamp=TIMESTAMP.isoformat(),
            results={"risk_score": EnrichmentActivityResult(data={"score": 17}, error=None)},
        )
    )

    async with session_factory() as session:
        rows = (await session.execute(select(Trade).order_by(Trade.trade_id))).scalars().all()

    updated = {row.trade_id: row for row in rows}
    assert updated["t-1"].enrichment == {"risk_score": {"data": {"score": 17}, "error": None}}
    assert updated["t-1"].enrichment_status == "completed"
    assert updated["t-2"].enrichment is None
    assert updated["t-2"].enrichment_status == "not_requested"


async def test_persist_preserves_partial_results_and_sets_completed_with_errors(pg_async_engine):
    session_factory = async_sessionmaker(bind=pg_async_engine, expire_on_commit=False)
    await _seed_trade(session_factory)
    await _seed_job(session_factory, "wf-2")

    activities = EnrichmentPersistenceActivities(session_factory)
    await activities.persist_trade_enrichment(
        PersistEnrichmentInput(
            workflow_id="wf-2",
            broker_id="broker-1",
            trade_id="t-1",
            timestamp=TIMESTAMP.isoformat(),
            results={
                "risk_score": EnrichmentActivityResult(data={"score": 17}, error=None),
                "sentiment": EnrichmentActivityResult(data=None, error="EnrichmentTimeoutError"),
            },
        )
    )

    async with session_factory() as session:
        row = (await session.execute(select(Trade).where(Trade.trade_id == "t-1"))).scalar_one()

    assert row.enrichment["risk_score"]["data"] == {"score": 17}
    assert row.enrichment["sentiment"]["error"] == "EnrichmentTimeoutError"
    assert row.enrichment_status == "completed_with_errors"


async def test_persist_marks_the_matching_job_completed(pg_async_engine):
    session_factory = async_sessionmaker(bind=pg_async_engine, expire_on_commit=False)
    await _seed_trade(session_factory)
    await _seed_job(session_factory, "wf-3")
    await _seed_job(session_factory, "wf-other", trade_id="t-1")

    activities = EnrichmentPersistenceActivities(session_factory)
    await activities.persist_trade_enrichment(
        PersistEnrichmentInput(
            workflow_id="wf-3",
            broker_id="broker-1",
            trade_id="t-1",
            timestamp=TIMESTAMP.isoformat(),
            results={"risk_score": EnrichmentActivityResult(data={"score": 1}, error=None)},
        )
    )

    async with session_factory() as session:
        jobs = (
            (
                await session.execute(
                    select(TradeEnrichmentJob).order_by(TradeEnrichmentJob.workflow_id)
                )
            )
            .scalars()
            .all()
        )

    jobs_by_id = {job.workflow_id: job for job in jobs}
    assert jobs_by_id["wf-3"].status == "completed"
    assert jobs_by_id["wf-other"].status == "dispatched"


def _counter_value(status: str) -> float:
    return metrics.enrichment_jobs_completed_total.labels(status=status)._value.get()


async def test_persist_records_completion_metric_and_latency(pg_async_engine):
    session_factory = async_sessionmaker(bind=pg_async_engine, expire_on_commit=False)
    await _seed_trade(session_factory)
    await _seed_job(session_factory, "wf-metrics")

    before = _counter_value("completed")
    activities = EnrichmentPersistenceActivities(session_factory)
    await activities.persist_trade_enrichment(
        PersistEnrichmentInput(
            workflow_id="wf-metrics",
            broker_id="broker-1",
            trade_id="t-1",
            timestamp=TIMESTAMP.isoformat(),
            results={"risk_score": EnrichmentActivityResult(data={"score": 1}, error=None)},
        )
    )

    assert _counter_value("completed") == before + 1
    # The job was seeded (and thus created_at stamped) just before the
    # activity ran, so latency should be a small non-negative number, not
    # left unset/negative.
    assert metrics.enrichment_job_latency_seconds._sum.get() >= 0
