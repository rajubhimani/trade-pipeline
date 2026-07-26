from copy import replace
from decimal import Decimal

from trade_pipeline.common.models import TradeEvent, new_trade_id


def make_event(**overrides) -> TradeEvent:
    defaults = {
        "broker_id": "broker-1",
        "trade_id": "t-1",
        "symbol": "AAPL",
        "qty": 10,
        "price": Decimal("190.50"),
    }
    defaults.update(overrides)
    return TradeEvent(**defaults)


def test_dedup_key_format():
    event = make_event(broker_id="broker-9", trade_id="abc123")
    assert event.dedup_key() == "trade:broker-9:abc123"


def test_event_is_frozen():
    event = make_event()
    try:
        event.qty = 99
    except AttributeError:
        pass
    else:
        raise AssertionError("TradeEvent should be immutable")


def test_copy_replace_updates_single_field():
    event = make_event(qty=10)
    updated = replace(event, qty=20)
    assert updated.qty == 20
    assert updated.trade_id == event.trade_id
    assert event.qty == 10  # original untouched


def test_new_trade_id_is_unique():
    assert new_trade_id() != new_trade_id()
