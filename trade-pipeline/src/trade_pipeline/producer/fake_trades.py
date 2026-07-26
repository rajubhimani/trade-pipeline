"""Kafka producer — simulates N broker feeds, publishes TradeEvents.

Uses the standard synchronous confluent-kafka Producer API (poll/produce loop),
which is still the stable, documented pattern — confluent-kafka's asyncio
AIOProducer is beta as of 2.13.0b1 and not used here (see docs/DECISIONS.md).
Intentionally re-sends ~5% of events with a duplicate trade_id to simulate
real-world broker duplicate delivery, which the consumer's Redis dedup layer
must handle.

Compression: zstd is enabled via Kafka's own ``compression.type`` producer
config (librdkafka-native), not hand-rolled per-message payload compression
with the stdlib ``compression.zstd`` module. This is the idiomatic choice —
Kafka compresses whole batches, which gets a far better ratio than
compressing tiny individual JSON messages one at a time would; the consumer
needs zero decompression code since librdkafka's Consumer decompresses
transparently. The stdlib ``compression.zstd`` module is still demonstrated
in this codebase where it's the right tool: batch cold-storage archival
files (see ``dagster_pipeline/archival.py``), which really are compressing
one large payload at a time.
"""

import json
import logging
import random
import time
from dataclasses import asdict
from decimal import Decimal

from confluent_kafka import Producer

from trade_pipeline.common.models import TradeEvent, new_trade_id

logger = logging.getLogger(__name__)

SYMBOLS = ("AAPL", "MSFT", "GOOG", "AMZN", "NVDA")
DUPLICATE_RATE = 0.05


def _serialize(event: TradeEvent) -> bytes:
    payload = asdict(event)
    payload["price"] = str(payload["price"])
    payload["timestamp"] = payload["timestamp"].isoformat()
    return json.dumps(payload).encode("utf-8")


def _delivery_report(err, _msg) -> None:
    # confluent_kafka's produce() callback signature requires (err, msg) —
    # msg (the delivered/failed Message) isn't needed here, only the error.
    if err is not None:
        logger.error("delivery failed: %s", err)


def _producer_config(bootstrap_servers: str) -> dict:
    return {"bootstrap.servers": bootstrap_servers, "compression.type": "zstd"}


def generate_trade(broker_id: str) -> TradeEvent:
    return TradeEvent(
        broker_id=broker_id,
        trade_id=new_trade_id(),
        symbol=random.choice(SYMBOLS),
        qty=random.randint(1, 500),
        price=Decimal(str(round(random.uniform(50, 500), 2))),
    )


def run_producer(
    bootstrap_servers: str,
    topic: str,
    broker_ids: tuple[str, ...] = ("broker-1", "broker-2", "broker-3"),
    event_count: int = 1000,
    sleep_seconds: float = 0.01,
) -> None:
    producer = Producer(_producer_config(bootstrap_servers))
    last_events: list[TradeEvent] = []

    for i in range(event_count):
        broker_id = random.choice(broker_ids)

        # Resend a recent event to simulate a duplicate broker delivery.
        if last_events and random.random() < DUPLICATE_RATE:
            event = random.choice(last_events)
        else:
            event = generate_trade(broker_id)
            last_events.append(event)
            if len(last_events) > 50:
                last_events.pop(0)

        producer.produce(topic, value=_serialize(event), callback=_delivery_report)
        producer.poll(0)
        if i % 100 == 0:
            logger.info("produced %d/%d events", i, event_count)
        time.sleep(sleep_seconds)

    producer.flush()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from trade_pipeline.common.config import load_config

    config = load_config()
    run_producer(config.kafka.bootstrap_servers, config.kafka.topic)
