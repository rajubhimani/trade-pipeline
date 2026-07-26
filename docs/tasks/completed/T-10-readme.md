# [done] README as design doc (component-3, docs) — id: T-10

Added: 2026-07-26
Completed: 2026-07-26
Notes: trade-pipeline/README.md rewritten as a standalone design doc: problem statement, mermaid
architecture diagram, a decision-rationale table (Kafka vs RabbitMQ, Redis vs DB dedup, RS256 vs
HS256, Postgres vs ClickHouse, Argon2id vs bcrypt, custom rate limiter vs slowapi, pure ASGI vs
BaseHTTPMiddleware, Temporal/Dagster placement, feature flags in Postgres vs env vars), a "what I'd
change at 10x scale" section, Python 3.11-vs-3.14 version notes, how-to-run instructions, and a
feature-flags usage section. Fixed a real bug caught while writing the how-to-run section: the
documented uvicorn command pointed at create_app directly, which isn't a valid zero-arg --factory
target (it requires engine/redis/settings args) — added build_production_app() as the actual
production entrypoint, verified it builds a working app with all routes present before documenting it.
Feature doc: not applicable (documentation task, not a code feature — see create-feature skill notes
on when a feature doc is warranted).
