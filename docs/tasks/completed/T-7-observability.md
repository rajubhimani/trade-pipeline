# [done] Observability — Prometheus metrics + structlog audit middleware (component-5) — id: T-7

Added: 2026-07-26
Completed: 2026-07-26
Notes: consumer lag, dedup hit rate, write p99, API p99. API-side (instrumentator /metrics,
AuditLogMiddleware) was already shipped in T-5 — this task covered the remaining consumer-process
metrics: dedup_hits_total/dedup_misses_total counters, a write-latency histogram around the Postgres
sink call, and a per-partition consumer-lag gauge, exposed via a small metrics HTTP server started
from the consumer's __main__ (prometheus_client.start_http_server on port 8001).
Wired into DedupConsumer.is_duplicate/process_message without changing its tested control flow — the
existing 7 dedup_consumer tests from T-4 pass unchanged, confirming metrics are purely observational.
7 new tests (tests/observability/test_metrics.py) using delta assertions (metrics are module-level
globals shared across the test session, so absolute-value assertions would be flaky) and an injectable
get_watermark_offsets callable for lag computation (no real broker needed).
60/60 tests passing project-wide, ruff clean, pip-audit clean.
Feature doc: docs/features/observability.md
