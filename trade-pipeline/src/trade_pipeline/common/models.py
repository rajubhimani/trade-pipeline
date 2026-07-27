"""Shared data models for the trade pipeline.

Written 3.14-native (deferred annotations, PEP 649 — no
``from __future__ import annotations`` needed). See docs/PYTHON_VERSION_NOTES.md
for the 3.11 fallback shape of each version-gated construct used here.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class TradeEvent:
    """One trade event as produced by a broker feed.

    ``frozen=True`` + ``slots=True``: immutable, memory-efficient — appropriate
    for a high-volume, short-lived message object. Updates go through
    ``copy.replace()`` (3.13+), not the older ``dataclasses.replace()``.
    # 3.11 fallback: dataclasses.replace(event, price=new_price) — same result,
    # dataclasses.replace() has existed since 3.7 and still works on 3.14, but
    # copy.replace() is the version-current spelling and also works on plain
    # objects with __replace__, not just dataclasses.
    """

    broker_id: str
    trade_id: str
    symbol: str
    qty: int
    price: Decimal
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def dedup_key(self) -> str:
        return f"trade:{self.broker_id}:{self.trade_id}"


def new_trade_id() -> str:
    return str(uuid4())
