"""Real enrichment service clients for the durable per-trade path.

Distinct from mock_services.py's ``MockServiceScript`` (a scripted sequence
of steps, used by tests and by the pre-existing demo/hand-rolled paths):
this module is what the Temporal activity actually calls in production —
either a real HTTP POST to a configured URL, or a deterministic demo
handler (varies by trade, not a fixed value) when no URL is configured for
a given service. See docs/features/async-enrichment.md.
"""

import hashlib

import aiohttp

from trade_pipeline.enrichment.mock_services import (
    EnrichmentBadRequestError,
    EnrichmentTimeoutError,
)
from trade_pipeline.enrichment.models import TradeEnrichmentPayload

_CALL_TIMEOUT_SECONDS = 2.0


def _demo_result(service_name: str, payload: TradeEnrichmentPayload) -> dict:
    """Deterministic per-trade output — same trade always yields the same
    demo result, but different trades don't collide, unlike a single fixed
    payload (see docs/features/async-enrichment.md's example result).

    A hash of the trade's own fields, nothing more — not a stand-in for a
    real risk model or sentiment classifier. Only meant to prove the
    orchestration (retry/timeout/persist-per-trade) behaves correctly when
    no real service is configured; swap in a real ``ENRICHMENT_*_URL`` for
    anything resembling actual scoring logic.
    """
    seed = f"{service_name}:{payload.broker_id}:{payload.trade_id}:{payload.timestamp}"
    digest = int(hashlib.sha256(seed.encode()).hexdigest(), 16)

    if service_name == "risk_score":
        return {"score": digest % 100, "trade_id": payload.trade_id}
    if service_name == "sentiment":
        labels = ["bullish", "neutral", "bearish"]
        return {"label": labels[digest % len(labels)], "trade_id": payload.trade_id}
    return {"trade_id": payload.trade_id}


async def call_service(service_name: str, payload: TradeEnrichmentPayload, url: str | None) -> dict:
    """Call one enrichment service for one trade.

    Raises ``EnrichmentBadRequestError`` (non-retryable) for HTTP 4xx, and
    ``EnrichmentTimeoutError`` (retryable) for timeouts, network failures,
    and HTTP 5xx — matching the retry policy already in
    ``temporal_workflow.EnrichmentWorkflow``.
    """
    if url is None:
        return _demo_result(service_name, payload)

    body = {
        "broker_id": payload.broker_id,
        "trade_id": payload.trade_id,
        "timestamp": payload.timestamp,
        "symbol": payload.symbol,
        "qty": payload.qty,
        "price": payload.price,
    }
    try:
        async with (
            aiohttp.ClientSession() as session,
            session.post(
                url, json=body, timeout=aiohttp.ClientTimeout(total=_CALL_TIMEOUT_SECONDS)
            ) as response,
        ):
            if 400 <= response.status < 500:
                text = await response.text()
                raise EnrichmentBadRequestError(
                    f"{service_name} returned {response.status}: {text}"
                )
            if response.status >= 500:
                raise EnrichmentTimeoutError(f"{service_name} returned {response.status}")
            return await response.json()
    except TimeoutError as exc:
        raise EnrichmentTimeoutError(f"{service_name} timed out") from exc
    except aiohttp.ClientError as exc:
        raise EnrichmentTimeoutError(f"{service_name} network error: {exc}") from exc
