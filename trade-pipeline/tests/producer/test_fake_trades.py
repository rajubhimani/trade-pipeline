import json
from decimal import Decimal

from trade_pipeline.producer.fake_trades import _producer_config, _serialize, generate_trade


def test_generate_trade_has_valid_symbol():
    event = generate_trade("broker-1")
    assert event.broker_id == "broker-1"
    assert event.symbol in {"AAPL", "MSFT", "GOOG", "AMZN", "NVDA"}
    assert 1 <= event.qty <= 500
    assert event.price > 0


def test_generate_trade_ids_are_unique():
    a = generate_trade("broker-1")
    b = generate_trade("broker-1")
    assert a.trade_id != b.trade_id


def test_serialize_round_trips_price_as_string():
    event = generate_trade("broker-2")
    raw = _serialize(event)
    payload = json.loads(raw)
    assert payload["broker_id"] == "broker-2"
    assert Decimal(payload["price"]) == event.price
    assert payload["trade_id"] == event.trade_id


def test_producer_config_enables_zstd_compression():
    config = _producer_config("localhost:9092")
    assert config["compression.type"] == "zstd"
    assert config["bootstrap.servers"] == "localhost:9092"
