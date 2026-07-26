"""Circuit breaker — 3 states, matches the plan's reference implementation.

One instance per enrichment service (never shared across services) — a
failing service's breaker tripping should not affect calls to a healthy one.
See docs/features/async-enrichment.md.

Deviation from the plan's reference code: ``call()`` takes a zero-arg
callable that *returns* the awaitable, not an already-created coroutine
object. Passing a live coroutine and then raising ``CircuitOpenError``
without ever awaiting it triggers a ``RuntimeWarning: coroutine '...' was
never awaited`` at garbage-collection time — which fails the test suite
outright under this project's ``filterwarnings = ["error::..."]`` policy.
Deferring creation until it's actually needed avoids the problem entirely.
"""

import time
from collections.abc import Awaitable, Callable
from enum import Enum, auto
from typing import TypeVar

T = TypeVar("T")


class CircuitState(Enum):
    CLOSED = auto()  # normal — requests pass through
    OPEN = auto()  # failing — reject immediately, no network call
    HALF_OPEN = auto()  # probing — allow exactly one request through


class CircuitOpenError(Exception):
    """Raised when a call is rejected because the circuit is open."""


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, recovery_timeout: float = 30.0):
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.last_failure_time = 0.0

    async def call(self, func: Callable[[], Awaitable[T]]) -> T:
        if self.state is CircuitState.OPEN:
            if time.monotonic() - self.last_failure_time > self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
            else:
                raise CircuitOpenError("circuit open — service unavailable")

        try:
            result = await func()
        except Exception:
            self._on_failure()
            raise
        else:
            self._on_success()
            return result

    def _on_success(self) -> None:
        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def _on_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.monotonic()
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
