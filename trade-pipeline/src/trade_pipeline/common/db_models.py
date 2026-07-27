"""Shared SQLAlchemy table definitions — Postgres only.

Table/column definitions are shared — the same ``Trade`` class backs both
the consumer's sync (``psycopg``) engine and the API's async (``asyncpg``)
engine. Only the Session/Engine machinery differs between the two call
sites (``consumer/postgres_sink.py`` vs ``api/dependencies.py``), which is
exactly why this lives in ``common`` instead of under either.

This project tests exclusively against a real Postgres (via Docker), not a
second dialect standing in for it — no dual-dialect hedging in the schema.
"""

from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Identity, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Trade(Base):
    """Range-partitioned by `timestamp` — see common/partitioning.py for the
    partition-creation DDL and docs/features/postgres-partitioning.md for
    the full rationale (append-heavy time-series table; partitioning keeps
    each partition small and turns "drop old data" into an instant
    DETACH PARTITION instead of a slow row-by-row DELETE).

    Composite primary key `(id, timestamp)`, not just `id`: Postgres
    requires every unique index/constraint on a partitioned table to
    include the partition key column — `id` alone as the sole PK is
    rejected outright for a `PARTITION BY RANGE` table. `id` still
    self-populates via `Identity()` (verified against a live Postgres
    container) despite being part of a composite key. Same reasoning
    extends `uq_broker_trade` to include `timestamp`; this doesn't weaken
    the dedup backstop (see docs/features/dedup-consumer.md) since a
    genuine duplicate delivery in this system is a broker resending the
    exact same event, timestamp included.
    """

    __tablename__ = "trades"
    __table_args__ = (
        UniqueConstraint("broker_id", "trade_id", "timestamp", name="uq_broker_trade"),
        {"postgresql_partition_by": "RANGE (timestamp)"},
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    broker_id: Mapped[str] = mapped_column(String(64), index=True)
    trade_id: Mapped[str] = mapped_column(String(64))
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    qty: Mapped[int]
    price: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    timestamp: Mapped[object] = mapped_column(DateTime(timezone=True), primary_key=True)
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
