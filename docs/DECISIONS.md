# Decisions log (ADR-lite)

One entry per non-obvious technical choice. Written so answers like "why Redis not DB for dedup" are
never re-derived from scratch — pulled from here, verified against current code before quoting.

---

### Redis SETNX for dedup, not a DB unique constraint
Redis in-memory ops are O(1) and sub-millisecond, needed to keep pace with per-event Kafka consumption
without becoming the bottleneck. A DB unique-constraint approach works but adds a round trip and a
failed-insert-as-control-flow pattern per duplicate, which is slower and noisier in logs. TTL (`EX 300`)
bounds memory since we only need a 5-minute dedup window.

### RS256 over HS256 for JWT
Asymmetric signing means only the auth service holds the private key; any service that only needs to
*verify* tokens (the query API) only needs the public key. HS256 would require distributing the shared
secret to every verifying service, which is a bigger blast radius if one is compromised.

### Postgres (hot) + local zstd archive (cold), not ClickHouse
The prep-plan's Q5 model answer uses ClickHouse for the hot path at real scale. This project is a
learning/demo build at low volume, so Postgres is enough to be genuinely queryable and keeps the
dependency count down; the README documents ClickHouse as the stated "what I'd change at 10x scale"
answer, per the plan's mock-interview guidance.

### Temporal for enrichment orchestration, not the ingestion hot path
See `ARCHITECTURE.md`. Short version: Temporal per-workflow overhead is fine for a bounded,
multi-service enrichment call with retries; it is the wrong tool for a tight per-Kafka-message loop
handling every trade event.

### Dagster for cold-storage batching, not live consumption
Same reasoning in the other direction — Dagster assets are for scheduled/triggered batch materialization
with observability, not per-message stream processing.

### uv over pip/poetry
Single fast tool for Python version management (3.11–3.14 side by side), dependency resolution, and
lockfiles. Matches the project's explicit goal of running/comparing multiple Python versions.
