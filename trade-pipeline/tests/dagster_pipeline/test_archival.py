from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from trade_pipeline.common.db_models import Base, Trade
from trade_pipeline.dagster_pipeline.archival import archive_pending_trades, read_archived_batch


@pytest.fixture
def engine():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def session_factory(engine):
    return sessionmaker(bind=engine)


def _seed_trades(session_factory, count: int) -> None:
    with session_factory() as session:
        for i in range(count):
            session.add(
                Trade(
                    broker_id="broker-1",
                    trade_id=f"t-{i}",
                    symbol="AAPL",
                    qty=1,
                    price=Decimal("100.00"),
                    timestamp=datetime(2026, 7, 26, tzinfo=UTC),
                )
            )
        session.commit()


def test_no_pending_trades_is_a_clean_noop(session_factory, tmp_path):
    with session_factory() as session:
        result = archive_pending_trades(session, tmp_path)

    assert result.archived_count == 0
    assert result.archive_path is None
    assert list(tmp_path.iterdir()) == []


def test_archives_pending_trades_and_writes_compressed_file(session_factory, tmp_path):
    _seed_trades(session_factory, 5)

    with session_factory() as session:
        result = archive_pending_trades(session, tmp_path)

    assert result.archived_count == 5
    assert result.archive_path is not None
    assert result.archive_path.exists()
    assert result.uncompressed_bytes > 0
    assert result.compressed_bytes > 0


def test_archived_rows_are_marked_and_excluded_from_next_run(session_factory, tmp_path):
    _seed_trades(session_factory, 3)

    with session_factory() as session:
        first = archive_pending_trades(session, tmp_path)
    assert first.archived_count == 3

    with session_factory() as session:
        rows = session.scalars(select(Trade)).all()
    assert all(row.archived for row in rows)

    with session_factory() as session:
        second = archive_pending_trades(session, tmp_path)
    assert second.archived_count == 0  # nothing left to archive


def test_batch_size_caps_a_single_run(session_factory, tmp_path):
    _seed_trades(session_factory, 10)

    with session_factory() as session:
        result = archive_pending_trades(session, tmp_path, batch_size=4)

    assert result.archived_count == 4

    with session_factory() as session:
        remaining = session.scalars(select(Trade).where(Trade.archived.is_(False))).all()
    assert len(remaining) == 6


def test_archive_file_round_trips_via_read_archived_batch(session_factory, tmp_path):
    _seed_trades(session_factory, 2)

    with session_factory() as session:
        result = archive_pending_trades(session, tmp_path)

    rows = read_archived_batch(result.archive_path)
    assert len(rows) == 2
    assert {row["trade_id"] for row in rows} == {"t-0", "t-1"}
    # Numeric(18, 4) normalizes precision on read-back from the DB.
    assert Decimal(rows[0]["price"]) == Decimal("100.00")


def test_compression_ratio_is_computed():
    from trade_pipeline.dagster_pipeline.archival import ArchiveResult

    result = ArchiveResult(
        archived_count=1, archive_path=None, uncompressed_bytes=200, compressed_bytes=50
    )
    assert result.compression_ratio == 4.0


def test_compression_ratio_is_zero_when_nothing_compressed():
    from trade_pipeline.dagster_pipeline.archival import ArchiveResult

    result = ArchiveResult(
        archived_count=0, archive_path=None, uncompressed_bytes=0, compressed_bytes=0
    )
    assert result.compression_ratio == 0.0
