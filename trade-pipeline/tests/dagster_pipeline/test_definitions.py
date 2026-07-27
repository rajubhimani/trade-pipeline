"""End-to-end test of the actual Dagster asset wiring, not just the
extracted archive_pending_trades logic — dg.materialize() runs the real
@asset in-process, no Dagster daemon/webserver needed.

DbEngineResource normally builds a fresh engine per get_engine() call
(would defeat this project's shared `pg_engine` fixture) — a fixture-scoped
subclass here pins that fixture's real engine instead.
"""

from datetime import UTC, datetime
from decimal import Decimal

import dagster as dg
import pytest
from sqlalchemy.orm import sessionmaker

from trade_pipeline.common.db_models import Trade
from trade_pipeline.dagster_pipeline.definitions import (
    AggregatesDirResource,
    ArchiveDirResource,
    DbEngineResource,
    archived_trades,
    daily_aggregate,
)


@pytest.fixture
def fixed_engine_resource(pg_engine):
    class _FixedEngineResource(DbEngineResource):
        def get_engine(self):
            return pg_engine

    return _FixedEngineResource(dsn="unused")


def test_materialize_archives_pending_trades(pg_engine, fixed_engine_resource, tmp_path):
    with sessionmaker(bind=pg_engine)() as session:
        session.add(
            Trade(
                broker_id="broker-1",
                trade_id="t-1",
                symbol="AAPL",
                qty=10,
                price=Decimal("190.50"),
                timestamp=datetime(2026, 7, 26, tzinfo=UTC),
            )
        )
        session.commit()

    result = dg.materialize(
        [archived_trades],
        resources={
            "db_engine": fixed_engine_resource,
            "archive_dir": ArchiveDirResource(path=str(tmp_path)),
        },
    )

    assert result.success
    (event,) = result.get_asset_materialization_events()
    metadata = event.materialization.metadata
    assert metadata["archived_count"].value == 1
    assert metadata["compressed_bytes"].value > 0


def test_materialize_is_a_noop_with_nothing_pending(fixed_engine_resource, tmp_path):
    result = dg.materialize(
        [archived_trades],
        resources={
            "db_engine": fixed_engine_resource,
            "archive_dir": ArchiveDirResource(path=str(tmp_path)),
        },
    )

    assert result.success
    (event,) = result.get_asset_materialization_events()
    assert event.materialization.metadata["archived_count"].value == 0


def test_daily_aggregate_materializes_after_archived_trades(
    pg_engine, fixed_engine_resource, tmp_path
):
    """Exercises the real asset dependency graph — daily_aggregate depends
    on archived_trades — not just the two assets in isolation.
    """
    with sessionmaker(bind=pg_engine)() as session:
        session.add(
            Trade(
                broker_id="broker-1",
                trade_id="t-1",
                symbol="AAPL",
                qty=42,
                price=Decimal("100.00"),
                timestamp=datetime(2026, 7, 26, tzinfo=UTC),
            )
        )
        session.commit()

    archive_dir = tmp_path / "archive"
    aggregates_dir = tmp_path / "aggregates"

    result = dg.materialize(
        [archived_trades, daily_aggregate],
        resources={
            "db_engine": fixed_engine_resource,
            "archive_dir": ArchiveDirResource(path=str(archive_dir)),
            "aggregates_dir": AggregatesDirResource(path=str(aggregates_dir)),
        },
    )

    assert result.success
    events = {
        e.materialization.asset_key.to_user_string(): e.materialization.metadata
        for e in result.get_asset_materialization_events()
    }
    assert events["archived_trades"]["archived_count"].value == 1
    aggregate_metadata = events["daily_aggregate"]
    assert aggregate_metadata["total_trades"].value == 1
    assert aggregate_metadata["output_path"].value is not None
