import asyncio

import pytest

from trade_pipeline.enrichment.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
)


async def _ok() -> str:
    return "ok"


async def _fail() -> str:
    raise ValueError("boom")


async def test_starts_closed():
    breaker = CircuitBreaker()
    assert breaker.state is CircuitState.CLOSED


async def test_successful_call_keeps_it_closed():
    breaker = CircuitBreaker()
    result = await breaker.call(_ok)
    assert result == "ok"
    assert breaker.state is CircuitState.CLOSED


async def test_opens_after_threshold_failures():
    breaker = CircuitBreaker(failure_threshold=3)
    for _ in range(3):
        with pytest.raises(ValueError):
            await breaker.call(_fail)
    assert breaker.state is CircuitState.OPEN


async def test_open_circuit_rejects_without_calling_through():
    breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=60)
    with pytest.raises(ValueError):
        await breaker.call(_fail)
    assert breaker.state is CircuitState.OPEN

    calls = []

    async def tracked() -> str:
        calls.append(1)
        return "should not run"

    with pytest.raises(CircuitOpenError):
        await breaker.call(tracked)
    assert calls == []  # never actually invoked


async def test_half_open_probe_success_closes_circuit():
    breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)
    with pytest.raises(ValueError):
        await breaker.call(_fail)
    assert breaker.state is CircuitState.OPEN

    await asyncio.sleep(0.02)  # past recovery_timeout
    result = await breaker.call(_ok)

    assert result == "ok"
    assert breaker.state is CircuitState.CLOSED


async def test_half_open_probe_failure_reopens_circuit():
    breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)
    with pytest.raises(ValueError):
        await breaker.call(_fail)

    await asyncio.sleep(0.02)
    with pytest.raises(ValueError):
        await breaker.call(_fail)

    assert breaker.state is CircuitState.OPEN
