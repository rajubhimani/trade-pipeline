"""Kafka consumer — Redis dedup, manual offset commit only after a successful write.

Dedup uses ``SETNX``-equivalent atomic set: ``redis.set(key, 1, nx=True, ex=ttl)``
returns ``True`` only if the key was newly created (see docs/DECISIONS.md for why
Redis over a DB unique constraint). Offset commit happens only after the sink
write succeeds — if the write raises, the consumer does not commit and Kafka
will redeliver the message on restart (at-least-once, never auto-commit).
"""

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

from confluent_kafka import Consumer, Message
from redis import Redis

from trade_pipeline.common.models import TradeEvent

logger = logging.getLogger(__name__)

SinkWriter = Callable[[TradeEvent], None]


def _deserialize(message: Message) -> TradeEvent:
    raw = json.loads(message.value())
    from datetime import datetime

    return TradeEvent(
        broker_id=raw["broker_id"],
        trade_id=raw["trade_id"],
        symbol=raw["symbol"],
        qty=raw["qty"],
        price=Decimal(raw["price"]),
        timestamp=datetime.fromisoformat(raw["timestamp"]),
    )


@dataclass(slots=True)
class DedupStats:
    processed: int = 0
    duplicates: int = 0

    @property
    def dedup_hit_rate(self) -> float:
        total = self.processed + self.duplicates
        return self.duplicates / total if total else 0.0


class DedupConsumer:
    """Wraps a Kafka Consumer with Redis-backed dedup and manual commit."""

    def __init__(self, redis_client: Redis, dedup_ttl_seconds: int, sink: SinkWriter):
        self._redis = redis_client
        self._ttl = dedup_ttl_seconds
        self._sink = sink
        self.stats = DedupStats()

    def is_duplicate(self, event: TradeEvent) -> bool:
        """True if this event was already seen within the dedup TTL window."""
        was_new = self._redis.set(event.dedup_key(), 1, nx=True, ex=self._ttl)
        return not was_new

    def process_message(self, message: Message) -> bool:
        """Process one Kafka message. Returns True if the caller should commit."""
        event = _deserialize(message)

        if self.is_duplicate(event):
            self.stats.duplicates += 1
            logger.debug("dropping duplicate %s", event.dedup_key())
            return True  # duplicates are safe to commit past — nothing to redo

        # Sink write must succeed before we allow the offset to be committed.
        self._sink(event)
        self.stats.processed += 1
        return True


def run_consumer(
    bootstrap_servers: str,
    topic: str,
    group_id: str,
    redis_client: Redis,
    dedup_ttl_seconds: int,
    sink: SinkWriter,
    max_messages: int | None = None,
) -> DedupStats:
    consumer = Consumer(
        {
            "bootstrap.servers": bootstrap_servers,
            "group.id": group_id,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,  # manual commit only after successful sink write
        }
    )
    consumer.subscribe([topic])
    dedup = DedupConsumer(redis_client, dedup_ttl_seconds, sink)

    handled = 0
    try:
        while max_messages is None or handled < max_messages:
            message = consumer.poll(timeout=1.0)
            if message is None:
                continue
            if message.error():
                logger.error("kafka error: %s", message.error())
                continue

            try:
                should_commit = dedup.process_message(message)
            except Exception:
                logger.exception("failed to process message, not committing offset")
                continue  # do not commit — message will be redelivered

            if should_commit:
                consumer.commit(message=message)
            handled += 1
    finally:
        consumer.close()

    return dedup.stats


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from trade_pipeline.common.config import load_config
    from trade_pipeline.consumer.postgres_sink import init_schema, make_engine, make_sink

    config = load_config()
    engine = make_engine(config.postgres.dsn.replace("+asyncpg", "+psycopg"))
    init_schema(engine)

    redis_client = Redis.from_url(config.redis.url)
    stats = run_consumer(
        bootstrap_servers=config.kafka.bootstrap_servers,
        topic=config.kafka.topic,
        group_id="dedup-consumer",
        redis_client=redis_client,
        dedup_ttl_seconds=config.redis.dedup_ttl_seconds,
        sink=make_sink(engine),
    )
    logger.info("processed=%d duplicates=%d", stats.processed, stats.duplicates)
