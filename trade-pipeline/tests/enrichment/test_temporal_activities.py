"""Activity-level tests — no Temporal runtime needed at all.

@activity.defn only changes how a function is registered with a worker; the
function itself is still a plain `async def` and can be awaited directly.
temporalio.testing.ActivityEnvironment additionally provides a mocked
activity context (heartbeat capture, cancellation) for anything that calls
`activity.heartbeat()` etc — not needed here since these activities don't.
"""

import pytest
from temporalio.exceptions import ApplicationError

from trade_pipeline.enrichment.mock_services import (
    always_bad_request,
    always_succeeds,
)
from trade_pipeline.enrichment.models import TradeEnrichmentPayload
from trade_pipeline.enrichment.temporal_workflow import (
    call_enrichment_service,
    register_service_script,
    register_service_url,
)


async def test_activity_returns_data_on_success():
    register_service_script("svc-a", always_succeeds({"score": 7}))
    result = await call_enrichment_service("svc-a")
    assert result.data == {"score": 7}
    assert result.error is None


async def test_activity_raises_non_retryable_application_error_for_bad_request():
    register_service_script("svc-b", always_bad_request())
    with pytest.raises(ApplicationError) as exc_info:
        await call_enrichment_service("svc-b")
    assert exc_info.value.non_retryable is True


def _payload(**overrides) -> TradeEnrichmentPayload:
    defaults = {
        "broker_id": "broker-1",
        "trade_id": "t-1",
        "timestamp": "2026-07-26T00:00:00+00:00",
        "symbol": "AAPL",
        "qty": 10,
        "price": "190.50",
        "service_names": ["risk_score", "sentiment"],
    }
    defaults.update(overrides)
    return TradeEnrichmentPayload(**defaults)


async def test_activity_with_payload_uses_deterministic_demo_handler_when_no_url_registered():
    register_service_url("risk_score", None)
    payload = _payload()

    result = await call_enrichment_service("risk_score", payload)

    assert result.error is None
    assert result.data["trade_id"] == "t-1"


async def test_activity_with_payload_differs_by_trade():
    register_service_url("risk_score", None)

    result_a = await call_enrichment_service("risk_score", _payload(trade_id="t-a"))
    result_b = await call_enrichment_service("risk_score", _payload(trade_id="t-b"))

    assert result_a.data != result_b.data
