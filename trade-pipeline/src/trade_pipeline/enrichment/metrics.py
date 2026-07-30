"""Prometheus metrics for the Temporal worker process (outbox dispatch +
enrichment persistence) — same pattern as ``observability/metrics.py`` for
the consumer: the worker is its own process with no FastAPI app to get
request-latency instrumentation for free, so it gets a small dedicated
``/metrics`` server of its own (see worker.py, docker-compose.yml).

Without this, "why hasn't this trade's enrichment shown up yet" has no
answer short of reading logs by hand — these three metrics turn that into a
dashboard query: dispatch rate, completion rate by outcome, and the
pending→persisted latency distribution.
"""

from prometheus_client import Counter, Histogram, start_http_server

enrichment_jobs_dispatched_total = Counter(
    "enrichment_jobs_dispatched_total",
    "Trade-enrichment outbox rows for which a workflow start was attempted "
    "(includes idempotent re-dispatches of an already-started workflow)",
)
enrichment_jobs_completed_total = Counter(
    "enrichment_jobs_completed_total",
    "Trade-enrichment workflows that persisted a result",
    labelnames=("status",),  # "completed" | "completed_with_errors"
)
enrichment_job_latency_seconds = Histogram(
    "enrichment_job_latency_seconds",
    "Time from an outbox job being created to its result being persisted",
)


def start_metrics_server(port: int) -> None:
    start_http_server(port)


def record_dispatch() -> None:
    enrichment_jobs_dispatched_total.inc()


def record_completion(*, status: str, latency_seconds: float) -> None:
    enrichment_jobs_completed_total.labels(status=status).inc()
    enrichment_job_latency_seconds.observe(latency_seconds)
