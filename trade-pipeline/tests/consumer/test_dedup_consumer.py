import json
from decimal import Decimal

from trade_pipeline.consumer.dedup_consumer import DedupConsumer


class FakeRedis:
    """Minimal fake matching the .set(key, value, nx=, ex=) surface we use."""

    def __init__(self):
        self._store: dict[str, object] = {}

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self._store:
            return None
        self._store[key] = value
        return True


class FakeMessage:
    def __init__(self, payload: dict):
        self._payload = payload

    def value(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def _payload(trade_id="t-1", broker_id="broker-1"):
    return {
        "broker_id": broker_id,
        "trade_id": trade_id,
        "symbol": "AAPL",
        "qty": 10,
        "price": "100.00",
        "timestamp": "2026-07-26T00:00:00+00:00",
    }


def test_first_event_is_processed_not_duplicate():
    sink_calls = []
    consumer = DedupConsumer(FakeRedis(), dedup_ttl_seconds=300, sink=sink_calls.append)

    committed = consumer.process_message(FakeMessage(_payload()))

    assert committed is True
    assert len(sink_calls) == 1
    assert sink_calls[0].price == Decimal("100.00")
    assert consumer.stats.processed == 1
    assert consumer.stats.duplicates == 0


def test_duplicate_event_is_dropped_not_sunk():
    sink_calls = []
    redis = FakeRedis()
    consumer = DedupConsumer(redis, dedup_ttl_seconds=300, sink=sink_calls.append)

    consumer.process_message(FakeMessage(_payload(trade_id="dup-1")))
    committed = consumer.process_message(FakeMessage(_payload(trade_id="dup-1")))

    assert committed is True  # duplicates still get their offset committed
    assert len(sink_calls) == 1  # sink only called once
    assert consumer.stats.processed == 1
    assert consumer.stats.duplicates == 1


def test_different_brokers_same_trade_id_are_not_duplicates():
    sink_calls = []
    consumer = DedupConsumer(FakeRedis(), dedup_ttl_seconds=300, sink=sink_calls.append)

    consumer.process_message(FakeMessage(_payload(trade_id="t-1", broker_id="broker-A")))
    consumer.process_message(FakeMessage(_payload(trade_id="t-1", broker_id="broker-B")))

    assert len(sink_calls) == 2
    assert consumer.stats.duplicates == 0


def test_dedup_hit_rate_stat():
    consumer = DedupConsumer(FakeRedis(), dedup_ttl_seconds=300, sink=lambda e: None)
    consumer.process_message(FakeMessage(_payload(trade_id="t-1")))
    consumer.process_message(FakeMessage(_payload(trade_id="t-1")))  # dup
    consumer.process_message(FakeMessage(_payload(trade_id="t-2")))

    assert consumer.stats.dedup_hit_rate == 1 / 3
