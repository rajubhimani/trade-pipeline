# Architecture — Real-Time Trade Event Pipeline

This doc tracks the actual system being built, kept in `trade-pipeline/`.

## 5-layer framework (applied to this system)

| Layer | Component | Tech |
|---|---|---|
| 1. Ingestion | Broker feed simulator | `confluent-kafka` producer, Kafka topic `trades` |
| 2. Processing | Dedup + normalize + enrich | Kafka consumer, Redis `SETNX ... EX 300`, async enrichment calls |
| 3. Storage | Hot / cold | Postgres (hot, queryable), S3-style local dir + `compression.zstd` (cold, archival) |
| 4. Query/Serve | Read API | FastAPI, async SQLAlchemy (`asyncpg`), JWT RS256 auth |
| 5. Monitoring | Metrics/alerts | Prometheus (`/metrics`), structured audit logs (`structlog`) |

## Where Temporal fits

Temporal owns **durable, multi-step workflows with retries/compensation** — not raw event ingestion.
Applied here to:

- **Per-trade enrichment workflow (live)**: `GET /trades` never calls Temporal or an enrichment
  service itself — it only reads whatever was already persisted. The consumer commits a trade and a
  pending `trade_enrichment_jobs` outbox row in one transaction; the Temporal worker's outbox
  dispatcher polls that table and starts one deterministic-ID `EnrichmentWorkflow` per trade, which
  runs the risk-score/sentiment activities concurrently and persists the (possibly partial) result
  back to the exact trade row. See `docs/features/async-enrichment.md` for the full design. The
  hand-rolled fan-out (`enrichment/hand_rolled.py`) stays in the codebase as the "how would you build
  this without a framework" interview answer (see `docs/DECISIONS.md`) but is no longer wired into
  the live route.
- **Refresh-token rotation** (`api/auth/refresh_workflow.py`) — a second, deliberately different
  Temporal pattern (single side-effecting operation, not a fan-out); not wired into the live
  `/auth/refresh` endpoint, kept as a worked comparison example.

Do NOT use Temporal for the hot-path dedup+write (per-event, sub-5s SLA, extremely high volume) —
that stays a plain async Kafka consumer. Temporal workflows have per-workflow overhead that doesn't
fit a tight per-message loop.

## Where Dagster fits

Dagster owns **batch/scheduled data-pipeline orchestration** — asset materialization, not live request
serving. Applied here to:

- **Cold storage archival job**: the "every 1000 trades → batch → zstd compress → write to `archive/`"
  step becomes a Dagster asset/job on a schedule or sensor (e.g. triggered by a Postgres row-count
  sensor or a simple cron schedule) instead of living inline in the consumer loop. Makes the batch job
  observable, retryable, and independently testable.
- Future: a daily Dagster job that reads cold storage and produces aggregate stats (dedup hit rate
  trends, volume per broker) — tracked in backlog.

## Explicit non-goals

- No Flink/Kafka Streams — plain Python async consumer is enough at this scale and keeps the "prove
  you understand the mechanics" value for interview prep.
- No Kubernetes — Docker Compose only, this is a learning project, not a deployment target.

## Directory layout (target)

```
trade-pipeline/
  pyproject.toml          # uv-managed, requires-python >=3.11,<3.15
  docker-compose.yml       # Kafka (KRaft), Redis, Postgres
  src/trade_pipeline/
    producer/              # Component 1 — Kafka producer, fake trades + dupes
    consumer/               # Component 2 — dedup consumer, manual offset commit
    api/                    # Component 3 — FastAPI query layer + auth
    enrichment/              # Component 4 — async enrichment, circuit breaker, Temporal workflow variant
    observability/           # Component 5 — Prometheus metrics, audit logging
    dagster_pipeline/        # Cold storage archival as Dagster assets/jobs
    common/                  # shared models, config, version-compat notes
  tests/                    # pytest, mirrors src/ layout
```

## Python version policy

Target `>=3.11,<3.15`. Default dev interpreter: 3.14 (newest stable). Every module that uses a
3.12+/3.14-only feature must have a comment noting the version floor and, where practical, a fallback
example — see `docs/PYTHON_VERSION_NOTES.md`. This is deliberate: the prep plan explicitly wants
"how would you handle this on 3.11 vs 3.14" answers, so the codebase should let you point at real
code for both.
