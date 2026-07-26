# Feature: Observability — consumer metrics + audit logging

Status: shipped
Task: docs/tasks/completed/T-7-observability.md

## Problem / motivation

Component 5 of the project (`../ARCHITECTURE.md`) — the plan's Week 6-7 model answer for the trade
pipeline explicitly lists the metrics that "separate senior from mid-level answers":
`consumer_lag_by_partition`, `dedup_hit_rate`, `write_latency_p99`, `api_request_latency_p99`. The API
half of this is already partially shipped (T-5 wired `prometheus-fastapi-instrumentator`'s `/metrics`
for request-latency histograms, and `AuditLogMiddleware` for `/auth/*` audit logs) — what's missing is
metrics from the **consumer process**, which isn't a FastAPI app and has no `/metrics` endpoint of its
own yet.

## Scope

In:
- `observability/metrics.py` — `prometheus_client` metrics for the consumer: dedup hit/miss counters,
  a write-latency histogram around the Postgres sink call, and a per-partition consumer-lag gauge.
- Wiring these into `consumer/dedup_consumer.py` without changing its existing tested behavior
  (dedup logic, commit sequencing) — metrics are observational, not control flow.
- A small metrics HTTP server (`prometheus_client.start_http_server`) started from the consumer's
  `__main__` block, since the consumer runs as its own process, separate from the API.

Out:
- Re-implementing API request-latency metrics — already covered by
  `prometheus-fastapi-instrumentator` in `api/main.py` (T-5); not duplicated here.
- Alerting/dashboards (Grafana, Alertmanager rules) — this project exposes metrics for scraping, it
  doesn't stand up a full monitoring stack. The plan's alert thresholds (e.g. "alert if lag > 10k
  events") are documented as guidance, not implemented as running alert rules.
- Producer-side metrics — the plan's model answer doesn't call for them; the producer is a load
  generator, not a production component being monitored.

## Design

- **Dedup hit rate**: `DedupConsumer` already tracks `processed`/`duplicates` counts in-process
  (`DedupStats`, from T-4) — this feature adds Prometheus `Counter`s incremented at the same call
  sites, so the existing tested dedup logic doesn't change, only gets observed.
- **Write latency**: a `Histogram` wraps the sink call inside `DedupConsumer.process_message`, timed
  with `time.perf_counter()` — measures the Postgres write specifically, not the whole message
  processing (which would also include the Redis round trip).
- **Consumer lag**: computed per partition as `high_watermark - 1 - message.offset()`, measured
  against the *current message's own offset*, not this consumer's committed offset — that reports "how
  far behind the tip is the message we just processed" (moves smoothly with throughput) rather than
  "how far behind is our last commit" (which would also reflect this consumer's own commit-batching
  behavior, muddying the signal). Uses `confluent_kafka.Consumer.get_watermark_offsets(partition,
  cached=True)` — cached, so it reads librdkafka's already-tracked high watermark from fetch responses
  instead of a broker round trip per message.
- Metrics module is a plain functions-over-globals module (not a class) — `prometheus_client`'s own
  registry is already a global, so wrapping it in another object adds indirection without benefit.

## Python version notes

No version-gated syntax needed; targets the full 3.11–3.14 range per `../PYTHON_VERSION_NOTES.md`.

## Testing plan

- 7 tests in `tests/observability/test_metrics.py` read metric values via the child sample's private
  `_value`/`collect()` (a commonly used, if technically private, pattern for testing
  `prometheus_client` metrics directly). Every assertion checks a **delta**, not an absolute value —
  metrics are module-level globals shared across the whole test session, so an absolute-value
  assertion would be flaky depending on test order.
- `DedupConsumer` tests from T-4 (7 tests) pass **unchanged** — metrics wiring was added at the same
  call sites without altering dedup/commit control flow, confirmed by re-running that suite untouched.
- Consumer-lag computation (`observe_consumer_lag`) tested against a `MagicMock` Kafka
  message/consumer double with an injectable `get_watermark_offsets` callable — no real broker needed,
  and covers: normal lag calculation, missing/uncached watermark (skips the observation rather than
  erroring), and lag never going negative (guards against a stale/inconsistent watermark read).
- 60/60 tests passing project-wide, ruff clean, pip-audit clean.
