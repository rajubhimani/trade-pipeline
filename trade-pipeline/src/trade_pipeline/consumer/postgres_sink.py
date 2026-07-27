"""Synchronous Postgres sink for the dedup consumer.

Sync on purpose: the consumer's poll loop (``dedup_consumer.run_consumer``) is a
plain blocking confluent-kafka loop, not an asyncio event loop — matching the
plan's Week 1-2 project track ("write the trade to Postgres using psycopg2 or
SQLAlchemy"), where async SQLAlchemy is reserved for the FastAPI query layer
(component 3) instead, since that's the process actually running an event
loop. Uses the ``psycopg`` (v3) driver — ``asyncpg`` (already a dependency) is
async-only and can't back a sync engine.

A unique constraint on (broker_id, trade_id) is kept as defense-in-depth even
though Redis is the primary dedup layer — if the Redis dedup key ever expired
early or Redis was temporarily down, this stops a duplicate row from landing
in Postgres, at the cost of turning that case into a raised error instead of a
silent duplicate (call sites must decide how to handle it; see
``write_trade``).
"""

from collections.abc import Callable

from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from trade_pipeline.common.db_models import Base, Trade
from trade_pipeline.common.models import TradeEvent
from trade_pipeline.common.partitioning import ensure_partitions


class DuplicateTradeError(Exception):
    """Raised when a trade already exists per the DB unique constraint.

    This should be rare in practice (Redis dedup already filters these out) —
    seeing it means the two dedup layers disagree and is worth alerting on,
    not silently swallowing.
    """


def make_engine(dsn: str):
    """Build a sync engine for the consumer's sink.

    Expects a plain ``postgresql+psycopg://`` DSN, distinct from the
    ``postgresql+asyncpg://`` DSN used by the FastAPI query layer — the two
    processes use different drivers for the reasons in this module's docstring.
    """
    return create_engine(dsn, pool_pre_ping=True)


def init_schema(engine) -> None:
    Base.metadata.create_all(engine)
    # trades is PARTITION BY RANGE (see Trade.__table_args__) — the ORM's
    # create_all emits the parent table DDL but can't create child
    # partitions on its own; without at least the DEFAULT partition, every
    # insert would be rejected outright.
    ensure_partitions(engine)


def make_sink(engine) -> Callable[[TradeEvent], None]:
    """Return a callable matching DedupConsumer's SinkWriter signature."""
    session_factory = sessionmaker(bind=engine)

    def write_trade(event: TradeEvent) -> None:
        with session_factory() as session:  # type: Session
            session.add(
                Trade(
                    broker_id=event.broker_id,
                    trade_id=event.trade_id,
                    symbol=event.symbol,
                    qty=event.qty,
                    price=event.price,
                    timestamp=event.timestamp,
                )
            )
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise DuplicateTradeError(event.dedup_key()) from exc

    return write_trade
