import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from trade_pipeline.consumer.dedup_consumer import DedupConsumer, run_consumer
from trade_pipeline.consumer.dlq import DlqPublishError


class FakeMessage:
    """Minimal stand-in for confluent_kafka.Message's .value() — not a
    service fake, just avoids needing a real Kafka message object to test
    pure deserialization/dedup logic.
    """

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


def test_first_event_is_processed_not_duplicate(redis_client):
    sink_calls = []
    consumer = DedupConsumer(redis_client, dedup_ttl_seconds=300, sink=sink_calls.append)

    committed = consumer.process_message(FakeMessage(_payload()))

    assert committed is True
    assert len(sink_calls) == 1
    assert sink_calls[0].price == Decimal("100.00")
    assert consumer.stats.processed == 1
    assert consumer.stats.duplicates == 0


def test_duplicate_event_is_dropped_not_sunk(redis_client):
    sink_calls = []
    consumer = DedupConsumer(redis_client, dedup_ttl_seconds=300, sink=sink_calls.append)

    consumer.process_message(FakeMessage(_payload(trade_id="dup-1")))
    committed = consumer.process_message(FakeMessage(_payload(trade_id="dup-1")))

    assert committed is True  # duplicates still get their offset committed
    assert len(sink_calls) == 1  # sink only called once
    assert consumer.stats.processed == 1
    assert consumer.stats.duplicates == 1


def test_different_brokers_same_trade_id_are_not_duplicates(redis_client):
    sink_calls = []
    consumer = DedupConsumer(redis_client, dedup_ttl_seconds=300, sink=sink_calls.append)

    consumer.process_message(FakeMessage(_payload(trade_id="t-1", broker_id="broker-A")))
    consumer.process_message(FakeMessage(_payload(trade_id="t-1", broker_id="broker-B")))

    assert len(sink_calls) == 2
    assert consumer.stats.duplicates == 0


def test_dedup_hit_rate_stat(redis_client):
    consumer = DedupConsumer(redis_client, dedup_ttl_seconds=300, sink=lambda e: None)
    consumer.process_message(FakeMessage(_payload(trade_id="t-1")))
    consumer.process_message(FakeMessage(_payload(trade_id="t-1")))  # dup
    consumer.process_message(FakeMessage(_payload(trade_id="t-2")))

    assert consumer.stats.dedup_hit_rate == 1 / 3


class _PollExhausted(Exception):
    """Raised by the fake poll() once its queued messages run out.

    The DLQ-skip paths (no dlq_producer, or the DLQ publish itself fails)
    never increment `handled`, so `run_consumer`'s `while ... handled <
    max_messages` loop can't terminate on its own — it would just poll()
    forever. Raising once queued messages are exhausted gives the test a
    deterministic point to stop at via `pytest.raises`, after the
    assertions we actually care about (mock call history) have already
    happened.
    """


def _mock_kafka_consumer(messages):
    remaining = list(messages)

    def poll(*_args, **_kwargs):
        if not remaining:
            raise _PollExhausted
        return remaining.pop(0)

    mock_consumer = MagicMock()
    mock_consumer.poll.side_effect = poll
    mock_consumer.commit = MagicMock()
    return mock_consumer


def test_run_consumer_sends_failing_message_to_dlq_and_commits(redis_client):
    def failing_sink(event):
        raise ValueError("simulated permanent failure")

    message = FakeMessage(_payload(trade_id="t-1"))
    message.error = lambda: None  # Message.error() -> None means no Kafka-level error
    message.topic = lambda: "trades"
    message.partition = lambda: 0
    message.offset = lambda: 7

    dlq_producer = MagicMock()

    with patch("trade_pipeline.consumer.dedup_consumer.Consumer") as MockConsumer:
        MockConsumer.return_value = _mock_kafka_consumer([message])

        run_consumer(
            bootstrap_servers="unused:9092",
            topic="trades",
            group_id="test-group",
            redis_client=redis_client,
            dedup_ttl_seconds=300,
            sink=failing_sink,
            dlq_producer=dlq_producer,
            max_messages=1,
        )

    dlq_producer.send.assert_called_once()
    sent_message, sent_error = dlq_producer.send.call_args.args
    assert sent_message is message
    assert isinstance(sent_error, ValueError)
    MockConsumer.return_value.commit.assert_called_once_with(message=message)


def test_run_consumer_does_not_commit_when_dlq_publish_fails(redis_client):
    def failing_sink(event):
        raise ValueError("simulated permanent failure")

    message = FakeMessage(_payload(trade_id="t-1"))
    message.error = lambda: None
    message.topic = lambda: "trades"
    message.partition = lambda: 0
    message.offset = lambda: 7

    dlq_producer = MagicMock()
    dlq_producer.send.side_effect = DlqPublishError("dlq unavailable")

    with patch("trade_pipeline.consumer.dedup_consumer.Consumer") as MockConsumer:
        MockConsumer.return_value = _mock_kafka_consumer([message])

        with pytest.raises(_PollExhausted):
            run_consumer(
                bootstrap_servers="unused:9092",
                topic="trades",
                group_id="test-group",
                redis_client=redis_client,
                dedup_ttl_seconds=300,
                sink=failing_sink,
                dlq_producer=dlq_producer,
                max_messages=1,
            )

    dlq_producer.send.assert_called_once()
    MockConsumer.return_value.commit.assert_not_called()


def test_run_consumer_without_dlq_producer_skips_without_committing(redis_client):
    """Backward compatibility: dlq_producer is optional, old behavior unchanged."""

    def failing_sink(event):
        raise ValueError("simulated permanent failure")

    message = FakeMessage(_payload(trade_id="t-1"))
    message.error = lambda: None
    message.topic = lambda: "trades"
    message.partition = lambda: 0
    message.offset = lambda: 7

    with patch("trade_pipeline.consumer.dedup_consumer.Consumer") as MockConsumer:
        MockConsumer.return_value = _mock_kafka_consumer([message])

        with pytest.raises(_PollExhausted):
            run_consumer(
                bootstrap_servers="unused:9092",
                topic="trades",
                group_id="test-group",
                redis_client=redis_client,
                dedup_ttl_seconds=300,
                sink=failing_sink,
                max_messages=1,
            )

    MockConsumer.return_value.commit.assert_not_called()
