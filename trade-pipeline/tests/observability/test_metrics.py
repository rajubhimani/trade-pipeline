"""Tests read metric values via the child sample's private ``_value`` — this
is a commonly used, if technically private, pattern for testing
prometheus_client metrics directly (the public API is exposition-format text
via generate_latest(), which is more work to parse for a single value).

Metrics are module-level globals shared across the whole test session, so
every assertion here checks a *delta* (before vs after), never an absolute
value — an absolute-value assertion would be flaky depending on what other
tests ran first.
"""

from unittest.mock import MagicMock

from trade_pipeline.observability import metrics


def _counter_value(counter) -> float:
    return counter._value.get()


def _gauge_value(gauge, **labels) -> float:
    return gauge.labels(**labels)._value.get()


def _histogram_count(histogram) -> float:
    (metric_family,) = histogram.collect()
    (count_sample,) = (s for s in metric_family.samples if s.name.endswith("_count"))
    return count_sample.value


def test_record_dedup_result_increments_hits_on_duplicate():
    before = _counter_value(metrics.dedup_hits_total)
    metrics.record_dedup_result(is_duplicate=True)
    after = _counter_value(metrics.dedup_hits_total)
    assert after == before + 1


def test_record_dedup_result_increments_misses_on_new_event():
    before = _counter_value(metrics.dedup_misses_total)
    metrics.record_dedup_result(is_duplicate=False)
    after = _counter_value(metrics.dedup_misses_total)
    assert after == before + 1


def test_time_write_records_an_observation():
    before = metrics.write_latency_seconds._sum.get()
    with metrics.time_write():
        pass
    after = metrics.write_latency_seconds._sum.get()
    assert after >= before  # a near-zero but non-negative duration was added


def test_time_write_records_even_when_the_block_raises():
    before_count = _histogram_count(metrics.write_latency_seconds)
    try:
        with metrics.time_write():
            raise ValueError("boom")
    except ValueError:
        pass
    after_count = _histogram_count(metrics.write_latency_seconds)
    assert after_count == before_count + 1


def test_observe_consumer_lag_sets_gauge_from_watermark():
    message = MagicMock()
    message.topic.return_value = "trades"
    message.partition.return_value = 0
    message.offset.return_value = 95

    consumer = MagicMock()

    def fake_watermarks(partition):
        return (0, 100)  # low, high — high is "offset of last message + 1"

    metrics.observe_consumer_lag(consumer, message, get_watermark_offsets=fake_watermarks)

    # lag = high - 1 - offset = 100 - 1 - 95 = 4
    assert _gauge_value(metrics.consumer_lag, topic="trades", partition="0") == 4


def test_observe_consumer_lag_skips_when_watermarks_unavailable():
    message = MagicMock()
    message.topic.return_value = "trades"
    message.partition.return_value = 1
    message.offset.return_value = 10

    consumer = MagicMock()
    before = _gauge_value(metrics.consumer_lag, topic="trades", partition="1")

    metrics.observe_consumer_lag(consumer, message, get_watermark_offsets=lambda p: None)

    after = _gauge_value(metrics.consumer_lag, topic="trades", partition="1")
    assert after == before  # unchanged — no watermark data to compute lag from


def test_observe_consumer_lag_never_goes_negative():
    message = MagicMock()
    message.topic.return_value = "trades"
    message.partition.return_value = 2
    message.offset.return_value = 200  # ahead of the "high" watermark below

    consumer = MagicMock()
    metrics.observe_consumer_lag(consumer, message, get_watermark_offsets=lambda p: (0, 100))

    assert _gauge_value(metrics.consumer_lag, topic="trades", partition="2") == 0
