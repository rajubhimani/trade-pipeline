# [done] Upgrade docker-compose to current stable pinned images (setup) — id: T-17

Added: 2026-07-26
Completed: 2026-07-26
Notes: Not from the original plan — requested mid-session ("upse[grade] post[g]ress 18.4 redis
8.8-alpine", "try to use latest stable docker images", "always use pinned version but latest stable",
"check for postgres and redis as well").
Upgraded: redis 7.4-alpine -> 8.8-alpine, postgres 17-alpine -> 18.4-alpine, and replaced
confluentinc/cp-kafka+cp-zookeeper 7.7.1 with apache/kafka:4.3.1 in KRaft mode (Zookeeper-based Kafka
is deprecated as of Kafka 4.x).
Every pinned tag verified against Docker Hub's registry API (digest match against that image's own
`latest` tag) before adopting, not assumed from memory — this caught a real breaking change: Postgres
18's image changed its expected data-directory mount point, which would have silently failed to start
with the old `docker-compose.yml` volume path (fixed: `/var/lib/postgresql` instead of
`/var/lib/postgresql/data`).
Ran a genuine end-to-end smoke test against the upgraded stack (not just "containers start"): created
the `trades` topic, ran the real producer against real Kafka, consumed via kafka-console-consumer to
confirm message format, ran the real consumer against real Kafka+Redis+Postgres end to end, and
confirmed rows landed in Postgres via psql. Full unit test suite (81/81) and ruff still pass unchanged
after the compose changes (no application code touched this task — infra/config only).
Feature doc: docs/features/uv-project-scaffold.md (docker-compose.yml is documented there, not a
separate feature doc, since it's the same "local dev services" scope as T-2).
