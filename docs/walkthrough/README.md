# Code walkthrough — index

A guided tour of the trade-pipeline codebase: what each piece does, how data flows between them, and
exactly where to click to see the real code. This is a companion to `../ARCHITECTURE.md` (the design)
and `../DECISIONS.md` (the "why") — this doc is the "here's the actual code, here's how it fits
together" tour.

**How to use this**: every code reference is a link with a GitHub line anchor (`file.py#L37`) — click
it to jump straight to that line on GitHub, or open the path locally. Each page has index/prev/next
navigation at the top and bottom so you can read it start to finish or jump around.

---

## Pages

| # | Page | Covers |
|---|---|---|
| 1 | [Project layout](01-project-layout.md) | Repo structure, docs system, how tasks/features/decisions relate |
| 2 | [Producer](02-producer.md) | Kafka producer, fake trade generation, duplicate simulation |
| 3 | [Consumer & storage](03-consumer-and-storage.md) | Redis dedup, manual offset commit, Postgres sink + partitioning |
| 4 | [API & auth](04-api-and-auth.md) | FastAPI app, JWT RS256, refresh tokens, middleware, rate limiting |
| 5 | [Enrichment](05-enrichment.md) | Hand-rolled circuit breaker vs Temporal workflow (comparison), plus the durable per-trade outbox dispatch that's actually live |
| 6 | [Dagster archival](06-dagster-archival.md) | Cold-storage batch job, zstd compression, resource-injected DB engine |
| 7 | [Python version comparisons](07-python-version-comparisons.md) | The old-vs-new demo module, feature by feature |
| 8 | [Testing & tooling](08-testing-and-tooling.md) | How the test suite is organized, ruff/pytest config, how to run everything |

## System overview

```mermaid
flowchart LR
    subgraph Ingestion
        P[Producer<br/>fake_trades.py]
    end
    subgraph Broker
        K[(Kafka topic: trades)]
    end
    subgraph Processing
        C[Consumer<br/>dedup_consumer.py]
        R[(Redis<br/>dedup keys)]
    end
    subgraph Storage
        PG[(Postgres<br/>trades + trade_enrichment_jobs)]
        ARC[(archive/<br/>zstd files)]
    end
    subgraph Serve
        API[FastAPI<br/>api/main.py]
        AUTH[JWT RS256 auth<br/>api/auth/]
    end
    subgraph Enrichment
        OB[Outbox dispatcher<br/>enrichment/outbox.py]
        TW[EnrichmentWorkflow<br/>Temporal worker]
        HR[Hand-rolled<br/>circuit breaker<br/>— unit-tested only,<br/>not in this flow]
    end
    subgraph Batch
        DAG[Dagster asset<br/>archived_trades]
    end

    P -->|produce, ~5% dupes| K
    K -->|poll| C
    C <-->|SETNX EX 300| R
    C -->|insert trade + pending job,<br/>one transaction| PG
    OB -->|poll pending jobs| PG
    OB -->|start workflow| TW
    TW -->|persist enrichment/<br/>enrichment_status| PG
    API -->|async SELECT<br/>reads stored enrichment only| PG
    API --> AUTH
    DAG -->|SELECT WHERE archived=false, every minute| PG
    DAG -->|zstd compress| ARC

    click P "02-producer.md" "Producer walkthrough"
    click C "03-consumer-and-storage.md" "Consumer walkthrough"
    click PG "03-consumer-and-storage.md" "Storage walkthrough"
    click API "04-api-and-auth.md" "API walkthrough"
    click OB "05-enrichment.md" "Enrichment walkthrough"
    click TW "05-enrichment.md" "Enrichment walkthrough"
    click HR "05-enrichment.md" "Enrichment walkthrough"
    click DAG "06-dagster-archival.md" "Dagster archival walkthrough"
    click ARC "06-dagster-archival.md" "Dagster archival walkthrough"
```

Enrichment is wired in durably, not as a live request-time fan-out: the consumer commits a trade and
a pending outbox job together, the Temporal worker's dispatcher starts one workflow per job, and the
workflow persists its result back to Postgres — `GET /trades` only ever reads what's already stored
(see [docs/features/async-enrichment.md](../features/async-enrichment.md)). The hand-rolled
circuit-breaker path still exists and is tested, but isn't reachable from this flow at all anymore.

---
[Index](README.md) · Next → [Project layout](01-project-layout.md)
