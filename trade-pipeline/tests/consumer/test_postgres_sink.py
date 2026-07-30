from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from trade_pipeline.common.db_models import FeatureFlag, TradeEnrichmentJob
from trade_pipeline.common.models import TradeEvent
from trade_pipeline.consumer.postgres_sink import (
    DuplicateTradeError,
    Trade,
    make_sink,
)
from trade_pipeline.enrichment.ids import compute_workflow_id


def make_event(**overrides) -> TradeEvent:
    defaults = {
        "broker_id": "broker-1",
        "trade_id": "t-1",
        "symbol": "AAPL",
        "qty": 10,
        "price": Decimal("190.50"),
        "timestamp": datetime(2026, 7, 26, tzinfo=UTC),
    }
    defaults.update(overrides)
    return TradeEvent(**defaults)


def test_write_trade_persists_row(pg_engine):
    sink = make_sink(pg_engine)
    sink(make_event())

    with sessionmaker(bind=pg_engine)() as session:
        rows = session.scalars(select(Trade)).all()

    assert len(rows) == 1
    assert rows[0].broker_id == "broker-1"
    assert rows[0].trade_id == "t-1"
    assert rows[0].price == Decimal("190.50")


def test_write_trade_raises_on_duplicate_broker_and_trade_id(pg_engine):
    sink = make_sink(pg_engine)
    sink(make_event(trade_id="dup-1"))

    with pytest.raises(DuplicateTradeError):
        sink(make_event(trade_id="dup-1"))

    with sessionmaker(bind=pg_engine)() as session:
        rows = session.scalars(select(Trade)).all()
    assert len(rows) == 1  # the failed duplicate insert did not leave a row


def test_write_trade_allows_same_trade_id_different_broker(pg_engine):
    sink = make_sink(pg_engine)
    sink(make_event(trade_id="t-1", broker_id="broker-A"))
    sink(make_event(trade_id="t-1", broker_id="broker-B"))

    with sessionmaker(bind=pg_engine)() as session:
        rows = session.scalars(select(Trade)).all()
    assert len(rows) == 2


def _set_enrichment_flag(pg_engine, enabled: bool) -> None:
    with sessionmaker(bind=pg_engine)() as session:
        session.add(FeatureFlag(name="enrichment_enabled", enabled=enabled))
        session.commit()


def test_write_trade_creates_pending_outbox_job_when_flag_enabled(pg_engine):
    _set_enrichment_flag(pg_engine, enabled=True)
    sink = make_sink(pg_engine)
    event = make_event(trade_id="t-enabled")

    sink(event)

    with sessionmaker(bind=pg_engine)() as session:
        trade = session.scalars(select(Trade).where(Trade.trade_id == "t-enabled")).one()
        jobs = session.scalars(select(TradeEnrichmentJob)).all()

    assert trade.enrichment_status == "pending"
    assert len(jobs) == 1
    job = jobs[0]
    assert job.workflow_id == compute_workflow_id(event.broker_id, event.trade_id, event.timestamp)
    assert job.status == "pending"
    assert job.payload["trade_id"] == "t-enabled"
    assert job.payload["service_names"] == ["risk_score", "sentiment"]


def test_write_trade_creates_no_outbox_job_when_flag_disabled(pg_engine):
    _set_enrichment_flag(pg_engine, enabled=False)
    sink = make_sink(pg_engine)

    sink(make_event(trade_id="t-disabled"))

    with sessionmaker(bind=pg_engine)() as session:
        trade = session.scalars(select(Trade).where(Trade.trade_id == "t-disabled")).one()
        jobs = session.scalars(select(TradeEnrichmentJob)).all()

    assert trade.enrichment_status == "not_requested"
    assert jobs == []


def test_write_trade_creates_no_outbox_job_when_flag_row_absent(pg_engine):
    # No FeatureFlag row at all — DEFAULT_FLAGS (common/feature_flags.py)
    # treats an absent row as disabled, same as the API path.
    sink = make_sink(pg_engine)

    sink(make_event(trade_id="t-no-flag-row"))

    with sessionmaker(bind=pg_engine)() as session:
        trade = session.scalars(select(Trade).where(Trade.trade_id == "t-no-flag-row")).one()
        jobs = session.scalars(select(TradeEnrichmentJob)).all()

    assert trade.enrichment_status == "not_requested"
    assert jobs == []
