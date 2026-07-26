"""Prometheus metrics for the consumer process.

The API process gets request-latency metrics for free from
``prometheus-fastapi-instrumentator`` (see api/main.py) — this module is for
the consumer, which is a separate process with no FastAPI app of its own to
attach that instrumentation to. Plain module-level metric objects, not
wrapped in a class: prometheus_client's registry is already a global, so
adding another object around it would be indirection without benefit.

Metric names follow Prometheus convention: ``_total`` suffix for counters,
``_seconds`` for time-based histograms.
"""

import time
from collections.abc import Callable, Generator
from contextlib import contextmanager

from confluent_kafka import Consumer, Message, TopicPartition
from prometheus_client import Counter, Gauge, Histogram, start_http_server

dedup_hits_total = Counter(
    "consumer_dedup_hits_total", "Trade events dropped as duplicates by the consumer"
)
dedup_misses_total = Counter(
    "consumer_dedup_misses_total", "New (non-duplicate) trade events processed by the consumer"
)
write_latency_seconds = Histogram(
    "consumer_write_latency_seconds", "Time spent writing one trade event to the sink"
)
consumer_lag = Gauge(
    "consumer_lag_messages",
    "Kafka consumer lag (high watermark - committed-so-far offset) per partition",
    labelnames=("topic", "partition"),
)


def start_metrics_server(port: int) -> None:
    start_http_server(port)


@contextmanager
def time_write() -> Generator[None, None, None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        write_latency_seconds.observe(time.perf_counter() - start)


def record_dedup_result(*, is_duplicate: bool) -> None:
    if is_duplicate:
        dedup_hits_total.inc()
    else:
        dedup_misses_total.inc()


def observe_consumer_lag(
    consumer: Consumer,
    message: Message,
    get_watermark_offsets: Callable[[TopicPartition], tuple[int, int] | None] | None = None,
) -> None:
    """Update the lag gauge for the partition `message` was read from.

    Lag is measured against the *current* message's own offset, not the
    consumer's committed offset — this reports "how far behind the tip is the
    message we just processed", which moves smoothly with throughput, rather
    than "how far behind is our last commit", which would also reflect this
    consumer's own commit-batching behavior. `get_watermark_offsets` is
    injectable (partition -> (low, high) | None) so tests don't need a real
    broker connection.

    `cached=True` on the real call uses librdkafka's already-tracked high
    watermark from fetch responses instead of a broker round trip per message.
    """
    fetch_watermarks = get_watermark_offsets or (
        lambda partition: consumer.get_watermark_offsets(partition, cached=True)
    )
    partition = TopicPartition(message.topic(), message.partition())
    watermarks = fetch_watermarks(partition)
    if watermarks is None:
        return  # cached watermark not yet available — skip this observation

    _low, high = watermarks
    lag = max(0, high - 1 - message.offset())
    consumer_lag.labels(topic=message.topic(), partition=str(message.partition())).set(lag)
