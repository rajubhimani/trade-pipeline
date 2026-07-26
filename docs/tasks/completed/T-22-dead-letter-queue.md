# [done] Dead-letter queue for the consumer (component-2) — id: T-22

Added: 2026-07-26
Completed: 2026-07-26
Notes: Not from the original plan — user asked directly for a DLQ, then for replay too. Feature doc
written first (docs/features/dead-letter-queue.md).
Shipped: consumer/dlq.py — DlqProducer.send() publishes a failed message's envelope (error type/
message, original topic/partition/offset, raw payload, failed_at) to `{topic}-dlq`, synchronous
(flushes before returning) so the caller only commits the original offset after a confirmed publish.
DlqPublishError propagates if the DLQ publish itself fails, so the original offset is NOT committed in
that case (falls back to the old redeliver-on-restart behavior — safer than losing the message).
Wired into run_consumer via an optional dlq_producer parameter (backward compatible — None preserves
the old skip-without-commit behavior exactly). Added consumer_dlq_total Prometheus counter.
Added a replay tool (replay_dlq / `python -m trade_pipeline.consumer.dlq --topic trades`) — reads
envelopes back off the DLQ topic and re-publishes the original payload to the original topic, a
deliberate batch tool a human runs on demand (stops when no more messages are currently pending),
committing its own consumer-group offset so re-running doesn't replay the same message twice.
11 new tests (4 DlqProducer unit tests with a fake Kafka producer, 3 run_consumer wiring tests using a
mocked confluent_kafka.Consumer — DLQ success commits, DLQ failure does not commit, no dlq_producer
preserves old behavior). 107/107 tests passing project-wide, ruff clean, pip-audit clean.
Feature doc: docs/features/dead-letter-queue.md
