from trade_pipeline.enrichment.circuit_breaker import CircuitBreaker, CircuitState
from trade_pipeline.enrichment.hand_rolled import enrich
from trade_pipeline.enrichment.mock_services import (
    always_bad_request,
    always_succeeds,
    always_times_out,
    fails_then_succeeds,
)


def _breakers(names: list[str], **kwargs) -> dict[str, CircuitBreaker]:
    return {name: CircuitBreaker(**kwargs) for name in names}


async def test_all_services_succeed():
    services = {
        "a": always_succeeds({"score": 1}).run,
        "b": always_succeeds({"score": 2}).run,
    }
    results = await enrich(services, _breakers(["a", "b"]))

    assert results["a"].data == {"score": 1}
    assert results["a"].error is None
    assert results["b"].data == {"score": 2}


async def test_service_retries_on_timeout_then_succeeds():
    script = fails_then_succeeds({"score": 5}, failures=2)
    services = {"a": script.run}

    results = await enrich(services, _breakers(["a"]))

    assert results["a"].data == {"score": 5}
    assert results["a"].error is None
    assert script.call_count == 3  # 2 failures + 1 success


async def test_service_exhausts_retries_and_degrades_gracefully():
    services = {"a": always_times_out().run}
    results = await enrich(services, _breakers(["a"]))

    assert results["a"].data is None
    assert results["a"].error == "EnrichmentTimeoutError"


async def test_bad_request_is_not_retried():
    script = always_bad_request()
    services = {"a": script.run}

    results = await enrich(services, _breakers(["a"]))

    assert results["a"].error == "EnrichmentBadRequestError"
    assert script.call_count == 1  # no retry attempts for a non-timeout error


async def test_one_failing_service_does_not_affect_others():
    services = {
        "good": always_succeeds({"score": 1}).run,
        "bad": always_times_out().run,
    }
    results = await enrich(services, _breakers(["good", "bad"]))

    assert results["good"].data == {"score": 1}
    assert results["bad"].data is None


async def test_open_circuit_rejects_without_calling_service():
    breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=60)
    script = always_times_out()

    # First call: fails, trips the breaker to OPEN.
    await enrich({"a": script.run}, {"a": breaker})
    assert breaker.state is CircuitState.OPEN
    calls_after_first_round = script.call_count

    # Second call: circuit is open, service must not be invoked again.
    results = await enrich({"a": script.run}, {"a": breaker})

    assert results["a"].error == "CircuitOpenError"
    assert script.call_count == calls_after_first_round
