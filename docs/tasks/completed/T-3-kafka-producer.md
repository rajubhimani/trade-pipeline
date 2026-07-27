# [done] Kafka producer — fake trades + 5% dupes (component-1) — id: T-3

Added: 2026-07-26
Completed: 2026-07-26
Notes: fake_trades.py done + unit tested (8 tests). Uses sync confluent-kafka Producer (not beta
AIOProducer). Compression: enabled via Kafka's native `compression.type: zstd` producer config, not
hand-rolled per-message `compression.zstd` (3.14 stdlib) as the plan literally names — deliberate
deviation, see docs/DECISIONS.md ("Kafka's native compression.type, not hand-rolled per-message
compression.zstd"). The stdlib module is still used where it's the right tool: Dagster archival
batches (T-8).
Verified end-to-end against a real Kafka broker (apache/kafka:4.3.1, KRaft) as part of the T-17 docker
image upgrade smoke test — produced real messages, consumed via kafka-console-consumer to confirm
format and that compression is transparent.
83/83 tests passing project-wide, ruff clean.
Feature doc: docs/features/kafka-producer.md
