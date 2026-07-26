from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from trade_pipeline.common.models import TradeEvent
from trade_pipeline.consumer.postgres_sink import (
    DuplicateTradeError,
    Trade,
    init_schema,
    make_sink,
)


@pytest.fixture
def engine():
    # SQLite in-memory stands in for Postgres for unit tests — no real DB needed.
    # Not used for anything Postgres-specific (JSONB, arrays, etc), so this is safe.
    eng = create_engine("sqlite:///:memory:")
    init_schema(eng)
    return eng


def make_event(**overrides) -> TradeEvent:
    defaults = dict(
        broker_id="broker-1",
        trade_id="t-1",
        symbol="AAPL",
        qty=10,
        price=Decimal("190.50"),
        timestamp=datetime(2026, 7, 26, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return TradeEvent(**defaults)


def test_write_trade_persists_row(engine):
    sink = make_sink(engine)
    sink(make_event())

    with sessionmaker(bind=engine)() as session:
        rows = session.scalars(select(Trade)).all()

    assert len(rows) == 1
    assert rows[0].broker_id == "broker-1"
    assert rows[0].trade_id == "t-1"
    assert rows[0].price == Decimal("190.50")


def test_write_trade_raises_on_duplicate_broker_and_trade_id(engine):
    sink = make_sink(engine)
    sink(make_event(trade_id="dup-1"))

    with pytest.raises(DuplicateTradeError):
        sink(make_event(trade_id="dup-1"))

    with sessionmaker(bind=engine)() as session:
        rows = session.scalars(select(Trade)).all()
    assert len(rows) == 1  # the failed duplicate insert did not leave a row


def test_write_trade_allows_same_trade_id_different_broker(engine):
    sink = make_sink(engine)
    sink(make_event(trade_id="t-1", broker_id="broker-A"))
    sink(make_event(trade_id="t-1", broker_id="broker-B"))

    with sessionmaker(bind=engine)() as session:
        rows = session.scalars(select(Trade)).all()
    assert len(rows) == 2
