"""Dead-letter queue — captures permanently-failing messages instead of
retrying them forever.

The "poison pill" problem: on a processing failure, the old behavior was to
log and skip committing, so Kafka would redeliver the same message from the
last committed offset on every restart/rebalance — correct for a transient
failure (a DB blip that succeeds on retry), wrong for a permanent one (a
message that will never process successfully no matter how many times it's
retried), which just generates the same failure forever. See
docs/features/dead-letter-queue.md.

Publishing to the DLQ and then committing the original offset anyway trades
"retry forever" for "capture it durably, keep the pipeline moving" — the
message isn't lost (a human or a future replay tool can read it back from
the DLQ topic), and it stops being reprocessed on every restart.
"""

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from confluent_kafka import Consumer, Message, Producer

logger = logging.getLogger(__name__)


class DlqPublishError(Exception):
    """Raised when publishing to the DLQ topic itself fails.

    Callers should treat this as "do not commit the original offset" — if
    the DLQ is unavailable, falling back to Kafka's own redelivery-on-restart
    is safer than silently dropping the message.
    """


@dataclass(frozen=True, slots=True)
class DlqProducer:
    producer: Producer
    dlq_topic_suffix: str = "-dlq"

    def dlq_topic_for(self, original_topic: str) -> str:
        return f"{original_topic}{self.dlq_topic_suffix}"

    def send(self, message: Message, error: Exception) -> None:
        """Publish `message`'s envelope to the DLQ topic for its origin topic.

        Synchronous (flushes immediately) rather than fire-and-forget: the
        caller only commits the original offset after this returns
        successfully, so a silent async failure here would defeat the whole
        point of the DLQ.
        """
        envelope = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "original_topic": message.topic(),
            "original_partition": message.partition(),
            "original_offset": message.offset(),
            "failed_at": datetime.now(UTC).isoformat(),
            "payload": message.value().decode("utf-8", errors="replace"),
        }

        delivery_errors: list[str] = []

        def _on_delivery(err, _msg) -> None:
            if err is not None:
                delivery_errors.append(str(err))

        dlq_topic = self.dlq_topic_for(message.topic())
        self.producer.produce(
            dlq_topic,
            value=json.dumps(envelope).encode("utf-8"),
            callback=_on_delivery,
        )
        self.producer.flush(timeout=10)

        if delivery_errors:
            raise DlqPublishError(f"failed to publish to {dlq_topic}: {delivery_errors[0]}")


def make_dlq_producer(bootstrap_servers: str) -> DlqProducer:
    return DlqProducer(producer=Producer({"bootstrap.servers": bootstrap_servers}))


def replay_dlq(
    bootstrap_servers: str,
    dlq_topic: str,
    group_id: str = "dlq-replay",
    max_messages: int | None = None,
) -> int:
    """Read envelopes off `dlq_topic` and re-publish each one's original
    payload to its original topic, so the normal consumer reprocesses it —
    the manual side of "capture it durably" (see module docstring).

    A batch tool, not a long-running service: stops as soon as no more
    messages are currently available (`poll()` returns `None`), rather than
    looping forever waiting for new ones — a human runs this deliberately
    ("replay the DLQ now"), it isn't a background process. Commits its own
    consumer-group offset on the DLQ topic as it replays, so re-running this
    tool doesn't replay the same message twice.
    """
    consumer = Consumer(
        {
            "bootstrap.servers": bootstrap_servers,
            "group.id": group_id,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )
    producer = Producer({"bootstrap.servers": bootstrap_servers})
    consumer.subscribe([dlq_topic])

    replayed = 0
    try:
        while max_messages is None or replayed < max_messages:
            message = consumer.poll(timeout=1.0)
            if message is None:
                break  # nothing currently pending — this batch run is done
            if message.error():
                logger.error("kafka error reading DLQ: %s", message.error())
                continue

            envelope = json.loads(message.value())
            target_topic = envelope["original_topic"]
            producer.produce(target_topic, value=envelope["payload"].encode("utf-8"))
            producer.flush(timeout=10)

            consumer.commit(message=message)
            replayed += 1
            logger.info(
                "replayed offset=%s from %s back to %s",
                envelope["original_offset"],
                dlq_topic,
                target_topic,
            )
    finally:
        consumer.close()

    return replayed


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Replay messages off a DLQ topic")
    parser.add_argument("--topic", required=True, help="original topic name, e.g. 'trades'")
    parser.add_argument("--bootstrap-servers", default=None)
    parser.add_argument("--max-messages", type=int, default=None)
    args = parser.parse_args()

    from trade_pipeline.common.config import load_config

    bootstrap_servers = args.bootstrap_servers or load_config().kafka.bootstrap_servers
    dlq_topic = f"{args.topic}-dlq"
    count = replay_dlq(bootstrap_servers, dlq_topic, max_messages=args.max_messages)
    logging.getLogger(__name__).info("replayed %d message(s) from %s", count, dlq_topic)
