"""Shared SQLAlchemy table definitions.

Table/column definitions are engine-agnostic in SQLAlchemy — the same
``Trade`` class backs both the consumer's sync (``psycopg``) engine and the
API's async (``asyncpg``) engine. Only the Session/Engine machinery differs
between the two call sites (``consumer/postgres_sink.py`` vs
``api/dependencies.py``), which is exactly why this lives in ``common``
instead of under either.
"""

from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Numeric, String, UniqueConstraint
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
    # Set True by the Dagster cold-storage archival job once a row has been
    # written to a compressed archive file — see dagster_pipeline/archival.py.
    # Python-side default only (no server_default): every insert already goes
    # through the ORM (postgres_sink.write_trade), so this is always set.
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class FeatureFlag(Base):
    """Feature flag state — toggled via a DB update (or the /admin/feature-flags
    API), not env vars/redeploys. See common/feature_flags.py.
    """

    __tablename__ = "feature_flags"

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
