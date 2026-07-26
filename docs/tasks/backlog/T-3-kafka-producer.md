# [in_progress] Kafka producer — fake trades + 5% dupes (component-1) — id: T-3

Added: 2026-07-26
Notes: fake_trades.py done + unit tested (7 tests). Uses sync confluent-kafka Producer (not beta AIOProducer).
Remaining: zstd compression for message payload on 3.14 (not yet added), config.toml wiring verified.
Feature doc: docs/features/kafka-producer.md
