"""End-to-end test of the actual Dagster asset wiring, not just the
extracted archive_pending_trades logic — dg.materialize() runs the real
@asset in-process, no Dagster daemon/webserver needed.

DbEngineResource normally builds a fresh engine per get_engine() call, which
would mean a *new*, empty ``sqlite:///:memory:`` database each time — a
subclass here pins one shared engine/schema for the test instead.
"""

from datetime import UTC, datetime
from decimal import Decimal

import dagster as dg
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from trade_pipeline.common.db_models import Base, Trade
from trade_pipeline.dagster_pipeline.definitions import (
    ArchiveDirResource,
    DbEngineResource,
    archived_trades,
)

_SHARED_ENGINE = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})


class _FixedEngineResource(DbEngineResource):
    def get_engine(self):
        return _SHARED_ENGINE


def _reset_schema():
    Base.metadata.drop_all(_SHARED_ENGINE)
    Base.metadata.create_all(_SHARED_ENGINE)


def test_materialize_archives_pending_trades(tmp_path):
    _reset_schema()
    with sessionmaker(bind=_SHARED_ENGINE)() as session:
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
            "db_engine": _FixedEngineResource(dsn="sqlite:///:memory:"),
            "archive_dir": ArchiveDirResource(path=str(tmp_path)),
        },
    )

    assert result.success
    (event,) = result.get_asset_materialization_events()
    metadata = event.materialization.metadata
    assert metadata["archived_count"].value == 1
    assert metadata["compressed_bytes"].value > 0


def test_materialize_is_a_noop_with_nothing_pending(tmp_path):
    _reset_schema()

    result = dg.materialize(
        [archived_trades],
        resources={
            "db_engine": _FixedEngineResource(dsn="sqlite:///:memory:"),
            "archive_dir": ArchiveDirResource(path=str(tmp_path)),
        },
    )

    assert result.success
    (event,) = result.get_asset_materialization_events()
    assert event.materialization.metadata["archived_count"].value == 0
