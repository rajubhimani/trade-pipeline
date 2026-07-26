"""Shared SQLAlchemy table definitions.

Table/column definitions are engine-agnostic in SQLAlchemy — the same
``Trade`` class backs both the consumer's sync (``psycopg``) engine and the
API's async (``asyncpg``) engine. Only the Session/Engine machinery differs
between the two call sites (``consumer/postgres_sink.py`` vs
``api/dependencies.py``), which is exactly why this lives in ``common``
instead of under either.
"""

from decimal import Decimal

from sqlalchemy import DateTime, Numeric, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Trade(Base):
    __tablename__ = "trades"
    __table_args__ = (UniqueConstraint("broker_id", "trade_id", name="uq_broker_trade"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    broker_id: Mapped[str] = mapped_column(String(64), index=True)
    trade_id: Mapped[str] = mapped_column(String(64))
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    qty: Mapped[int]
    price: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    timestamp: Mapped[object] = mapped_column(DateTime(timezone=True))
