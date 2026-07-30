"""Shared dataclasses for the durable per-trade enrichment path.

Split out from ``temporal_workflow.py``/``persistence.py``/``outbox.py`` so
those three modules can import the same wire types from one place without a
circular import (the workflow module needs to pass these into activities the
persistence module also needs to accept, and the outbox module constructs
them from the DB row it dispatches).
"""

from dataclasses import dataclass

# The two demo enrichment services this project wires up end to end — see
# docs/features/async-enrichment.md. A real deployment could pass a longer
# list; nothing here assumes exactly two.
DEFAULT_SERVICE_NAMES: list[str] = ["risk_score", "sentiment"]


@dataclass(frozen=True, slots=True)
class TradeEnrichmentPayload:
    """Immutable snapshot of one trade, captured at ingestion time.

    Timestamp and price are carried as strings (ISO 8601 / decimal text),
    not ``datetime``/``Decimal``, so this dataclass round-trips cleanly
    through both the ``trade_enrichment_jobs.payload`` JSONB column and
    Temporal's JSON data converter without relying on either to know about
    non-JSON-native Python types.
    """

    broker_id: str
    trade_id: str
    timestamp: str
    symbol: str
    qty: int
    price: str
    service_names: list[str]


@dataclass(frozen=True, slots=True)
class EnrichmentActivityResult:
    data: dict | None
    error: str | None


@dataclass(frozen=True, slots=True)
class EnrichmentWorkflowInput:
    """``payload`` is ``None`` only for the pre-existing demo/test path that
    calls ``EnrichmentWorkflow`` with bare service names and no trade to
    persist against (see test_temporal_workflow.py) — the real per-trade
    dispatch path (outbox.py) always supplies one.
    """

    service_names: list[str]
    payload: TradeEnrichmentPayload | None = None


@dataclass(frozen=True, slots=True)
class PersistEnrichmentInput:
    workflow_id: str
    broker_id: str
    trade_id: str
    timestamp: str
    results: dict[str, EnrichmentActivityResult]
