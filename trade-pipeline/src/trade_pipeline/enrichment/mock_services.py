"""Fake enrichment services — configurable latency/failure, shared by both
the hand-rolled and Temporal implementations and their tests.

Not real network calls (no aiohttp session, no actual service) — this
project's enrichment layer is a demo of the orchestration patterns, not a
real integration, so the "service" is just an async function with tunable
behavior.
"""

import asyncio
from dataclasses import dataclass, field


class EnrichmentTimeoutError(Exception):
    """Raised when a mock service takes too long — the retryable case."""


class EnrichmentBadRequestError(Exception):
    """Raised for a permanent, non-retryable failure (the '4xx' case)."""


@dataclass(slots=True)
class MockServiceScript:
    """Drives a sequence of scripted behaviors for one mock service call.

    Each call to ``run()`` consumes the next scripted step; once the script
    is exhausted the last step repeats. A step is either a plain return value
    or an exception instance to raise.
    """

    steps: list[object]
    delay_seconds: float = 0.0
    call_count: int = field(default=0, init=False)

    async def run(self) -> dict:
        index = min(self.call_count, len(self.steps) - 1)
        step = self.steps[index]
        self.call_count += 1

        if self.delay_seconds:
            await asyncio.sleep(self.delay_seconds)

        if isinstance(step, Exception):
            raise step
        return step


def always_succeeds(payload: dict) -> MockServiceScript:
    return MockServiceScript(steps=[payload])


def fails_then_succeeds(payload: dict, failures: int = 1) -> MockServiceScript:
    steps: list[object] = [EnrichmentTimeoutError("timed out")] * failures
    steps.append(payload)
    return MockServiceScript(steps=steps)


def always_times_out() -> MockServiceScript:
    return MockServiceScript(steps=[EnrichmentTimeoutError("timed out")])


def always_bad_request() -> MockServiceScript:
    return MockServiceScript(steps=[EnrichmentBadRequestError("bad request")])
