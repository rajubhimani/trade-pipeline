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
| 5 | [Enrichment](05-enrichment.md) | Hand-rolled circuit breaker vs Temporal workflow, side by side |
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
        PG[(Postgres<br/>trades table)]
        ARC[(archive/<br/>zstd files)]
    end
    subgraph Serve
        API[FastAPI<br/>api/main.py]
        AUTH[JWT RS256 auth<br/>api/auth/]
    end
    subgraph Enrichment
        HR[Hand-rolled<br/>circuit breaker]
        TW[Temporal<br/>workflow]
    end
    subgraph Batch
        DAG[Dagster asset<br/>archived_trades]
    end

    P -->|produce, ~5% dupes| K
    K -->|poll| C
    C <-->|SETNX EX 300| R
    C -->|manual commit after write| PG
    API -->|async SELECT| PG
    API --> AUTH
    API -.optional fan-out.-> HR
    API -.optional fan-out.-> TW
    DAG -->|SELECT WHERE archived=false, every minute| PG
    DAG -->|zstd compress| ARC

    click P "02-producer.md" "Producer walkthrough"
    click C "03-consumer-and-storage.md" "Consumer walkthrough"
    click PG "03-consumer-and-storage.md" "Storage walkthrough"
    click API "04-api-and-auth.md" "API walkthrough"
    click HR "05-enrichment.md" "Enrichment walkthrough"
    click TW "05-enrichment.md" "Enrichment walkthrough"
    click DAG "06-dagster-archival.md" "Dagster archival walkthrough"
    click ARC "06-dagster-archival.md" "Dagster archival walkthrough"
```

Enrichment isn't wired into the live `GET /trades` endpoint yet (see
[docs/features/async-enrichment.md](../features/async-enrichment.md) scope) — the dashed arrows above
mark that it's a standalone, tested component, not yet in the request path.

---
[Index](README.md) · Next → [Project layout](01-project-layout.md)
