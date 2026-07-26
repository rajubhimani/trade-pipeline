# [done] Consumer + Redis dedup + manual offset commit (component-2) — id: T-4

Added: 2026-07-26
Completed: 2026-07-26
Notes: dedup_consumer.py done, unit tested (4 tests) against fakes, no real Kafka/Redis needed for these.
Postgres sink (T-4b) now wired via `__main__` block — feature complete apart from a real end-to-end
Docker Compose smoke test (deferred, tracked implicitly under T-9/testing).
Feature doc: docs/features/dedup-consumer.md
