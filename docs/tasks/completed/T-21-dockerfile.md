# [done] Application Dockerfile (setup) — id: T-21

Added: 2026-07-26
Completed: 2026-07-26
Notes: Not from the original plan — user asked directly whether the project needs a Dockerfile.
docker-compose.yml only containerized infra (Kafka/Redis/Postgres); the app itself ran via `uv run` on
the host only. Feature doc written first (docs/features/dockerfile.md), verified current uv Dockerfile
best practice via research before writing anything (multi-stage build, --locked not --frozen,
UV_LINK_MODE=copy for cache mounts, PATH activation over `uv run` at runtime).
Shipped: single multi-stage Dockerfile producing one image for all four entrypoints (producer,
consumer, API, Dagster), selected via command override per docker-compose service rather than four
separate Dockerfiles. .dockerignore added.
Verified for real, not just trusted to compile: built the image, then ran the producer, API
(build_production_app), and consumer entrypoints inside the built image against the real
docker-compose Postgres/Redis/Kafka containers, and confirmed Dagster's `defs` imports correctly.
Cleaned up all test containers/images afterward.
Feature doc: docs/features/dockerfile.md
