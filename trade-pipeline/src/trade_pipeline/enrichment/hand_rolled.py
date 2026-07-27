"""Hand-rolled async enrichment fan-out — the "build it from memory" answer.

Full production pattern per the plan's Week 4 project track: per-service
retry (only on timeout, never on a bad-request-shaped error) + a hard
wait_for timeout + a circuit breaker per service, fanned out with
gather(return_exceptions=True) so one service's failure degrades that one
field to null instead of failing the whole response.

Kept alongside the Temporal version (temporal_workflow.py) deliberately —
see docs/features/async-enrichment.md and docs/ARCHITECTURE.md for why both
exist.
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from trade_pipeline.enrichment.circuit_breaker import CircuitBreaker, CircuitOpenError
from trade_pipeline.enrichment.mock_services import EnrichmentTimeoutError

CALL_TIMEOUT_SECONDS = 2.0


@dataclass(frozen=True, slots=True)
class EnrichmentResult:
    data: dict | None
    error: str | None


def _retrying_call(
    service_call: Callable[[], Awaitable[dict]],
) -> Callable[[], Awaitable[dict]]:
    """Wrap a service call with retry-on-timeout-only, matching the plan's
    explicit callout that retrying a bad-request-shaped error is wrong.
    """

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.01, min=0.01, max=0.05),
        retry=retry_if_exception_type((asyncio.TimeoutError, EnrichmentTimeoutError)),
        reraise=True,
    )
    async def call() -> dict:
        return await asyncio.wait_for(service_call(), timeout=CALL_TIMEOUT_SECONDS)

    return call


async def call_one_service(
    name: str,
    service_call: Callable[[], Awaitable[dict]],
    breaker: CircuitBreaker,
) -> tuple[str, EnrichmentResult]:
    try:
        data = await breaker.call(_retrying_call(service_call))
    except Exception as exc:
        return name, EnrichmentResult(data=None, error=type(exc).__name__)
    else:
        return name, EnrichmentResult(data=data, error=None)


async def enrich(
    services: dict[str, Callable[[], Awaitable[dict]]],
    breakers: dict[str, CircuitBreaker],
) -> dict[str, EnrichmentResult]:
    """Fan out to every service in parallel; a failing/open-circuit service
    degrades to a null result instead of failing the whole call.
    """
    tasks = [
        call_one_service(name, call, breakers[name]) for name, call in services.items()
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    merged: dict[str, EnrichmentResult] = {}
    for name, result in zip(services.keys(), results, strict=True):
        if isinstance(result, BaseException):
            # A bug in call_one_service itself, not a service failure — it
            # already catches service-level exceptions, so this branch is
            # only reachable for something like a cancellation.
            merged[name] = EnrichmentResult(data=None, error=type(result).__name__)
        else:
            merged[name] = result[1]
    return merged


__all__ = ["CircuitOpenError", "EnrichmentResult", "enrich"]
