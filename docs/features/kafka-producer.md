# Feature: Kafka producer — fake trade events

Status: in progress
Task: docs/tasks/backlog/T-3-kafka-producer.md

## Problem / motivation

Component 1 of the project (`../ARCHITECTURE.md`): the pipeline needs a data source. Real broker
feeds aren't available for a learning project, so a producer simulates N broker feeds, including the
duplicate-delivery behavior the rest of the pipeline (Redis dedup) exists to handle.

## Scope

In: `src/trade_pipeline/producer/fake_trades.py` — generates `TradeEvent`s across a configurable set
of broker ids, publishes to a Kafka topic, and re-sends ~5% of recently-produced events unchanged to
simulate duplicate delivery.

Out: real market data, backpressure/throughput tuning, schema registry (Avro/Protobuf) — plain JSON
payloads are enough for this project's purpose.

## Design

- Uses `confluent_kafka.Producer` (synchronous, poll/produce loop) — the standard, stable API.
  `confluent-kafka` does have a beta `AIOProducer` (2.13.0b1) but beta async APIs aren't used for this
  build; see `../DECISIONS.md`.
- `TradeEvent` (from `common/models.py`) is serialized to JSON with `Decimal` price and `datetime`
  timestamp converted to string forms for JSON-safety, then decoded back symmetrically in the consumer.
- Duplicate simulation keeps a small rolling window (last 50 events) and, with `DUPLICATE_RATE = 0.05`
  probability, re-emits one verbatim instead of generating a new event — this is what makes the
  consumer's dedup logic exercise real duplicate `trade_id`s rather than only unique ones.

## Python version notes

No 3.12+/3.14-only syntax used here — this module targets the full 3.11–3.14 range without a fallback
comment needed (see `../PYTHON_VERSION_NOTES.md`). Candidate future addition: `compression.zstd`
(3.14 stdlib) for payload compression, currently unimplemented (tracked as remaining work on T-3).

## Testing plan

Unit tests in `tests/producer/test_fake_trades.py` (7 tests, passing): trade generation stays within
valid ranges, trade ids are unique across calls, and JSON serialization round-trips the `Decimal`
price correctly. No live Kafka broker required for these — `run_producer()` itself (the part that
talks to a real broker) is not yet covered by an integration test; that requires Docker Compose up
and is deferred until the end-to-end smoke test task.
