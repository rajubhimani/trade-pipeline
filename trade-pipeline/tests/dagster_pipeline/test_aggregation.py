from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy.orm import sessionmaker

from trade_pipeline.common.db_models import Trade
from trade_pipeline.dagster_pipeline.aggregation import aggregate_archive_directory
from trade_pipeline.dagster_pipeline.archival import archive_pending_trades


@pytest.fixture
def session_factory(pg_engine):
    return sessionmaker(bind=pg_engine)


def _seed_and_archive(session_factory, archive_dir, trades: list[dict]) -> None:
    with session_factory() as session:
        for t in trades:
            defaults = {
                "broker_id": "broker-1",
                "trade_id": "t-1",
                "symbol": "AAPL",
                "qty": 1,
                "price": Decimal("100.00"),
                "timestamp": datetime(2026, 7, 26, tzinfo=UTC),
            }
            defaults.update(t)
            session.add(Trade(**defaults))
        session.commit()

    with session_factory() as session:
        archive_pending_trades(session, archive_dir)


def test_empty_archive_directory_is_a_clean_noop(tmp_path):
    result = aggregate_archive_directory(tmp_path)
    assert result.total_trades == 0
    assert result.volume_by_broker == {}
    assert result.count_by_symbol == {}
    assert result.output_path is None


def test_aggregates_volume_by_broker_and_count_by_symbol(session_factory, tmp_path):
    _seed_and_archive(
        session_factory,
        tmp_path,
        [
            {"trade_id": "t-1", "broker_id": "broker-A", "symbol": "AAPL", "qty": 10},
            {"trade_id": "t-2", "broker_id": "broker-A", "symbol": "MSFT", "qty": 5},
            {"trade_id": "t-3", "broker_id": "broker-B", "symbol": "AAPL", "qty": 20},
        ],
    )

    result = aggregate_archive_directory(tmp_path)

    assert result.total_trades == 3
    assert result.volume_by_broker == {"broker-A": 15, "broker-B": 20}
    assert result.count_by_symbol == {"AAPL": 2, "MSFT": 1}


def test_aggregates_across_multiple_archive_files(session_factory, tmp_path):
    _seed_and_archive(session_factory, tmp_path, [{"trade_id": "t-1", "qty": 5}])
    _seed_and_archive(session_factory, tmp_path, [{"trade_id": "t-2", "qty": 7}])

    result = aggregate_archive_directory(tmp_path)

    assert result.total_trades == 2
    assert result.volume_by_broker == {"broker-1": 12}


def test_writes_output_file_when_output_dir_given(session_factory, tmp_path):
    archive_dir = tmp_path / "archive"
    output_dir = tmp_path / "aggregates"
    _seed_and_archive(session_factory, archive_dir, [{"trade_id": "t-1", "qty": 3}])

    result = aggregate_archive_directory(archive_dir, output_dir=output_dir)

    assert result.output_path is not None
    assert result.output_path.exists()
    assert result.output_path.parent == output_dir


def test_no_output_file_written_when_output_dir_omitted(session_factory, tmp_path):
    _seed_and_archive(session_factory, tmp_path, [{"trade_id": "t-1"}])
    result = aggregate_archive_directory(tmp_path)
    assert result.output_path is None
