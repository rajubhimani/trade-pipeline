"""Dagster asset + schedule wiring — thin wrapper around archival.py.

Run standalone with `dagster dev -m trade_pipeline.dagster_pipeline.definitions`
(from trade-pipeline/) to see it in the Dagster UI. The asset itself defers
all real logic to archive_pending_trades — this module only adapts that
function's return value into Dagster's metadata/reporting shape.

The DB engine is injected via a Dagster resource rather than loaded from
config inside the asset — same dependency-injection reasoning as
api/main.py's create_app() factory: it lets tests swap in a SQLite
in-memory engine via dg.materialize(..., resources=...) instead of needing a
real Postgres connection, and lets dg.materialize() actually exercise the
real asset/resource wiring, not just the extracted pure logic.
"""

from pathlib import Path

import dagster as dg
from sqlalchemy import Engine
from sqlalchemy.orm import sessionmaker

from trade_pipeline.common.config import load_config
from trade_pipeline.consumer.postgres_sink import make_engine
from trade_pipeline.dagster_pipeline.archival import archive_pending_trades

DEFAULT_ARCHIVE_DIR = Path(__file__).parent.parent.parent.parent / "archive"


class DbEngineResource(dg.ConfigurableResource):
    dsn: str

    def get_engine(self) -> Engine:
        return make_engine(self.dsn)


class ArchiveDirResource(dg.ConfigurableResource):
    path: str = str(DEFAULT_ARCHIVE_DIR)


@dg.asset(description="Batch not-yet-archived trades, zstd-compress, write to archive/")
def archived_trades(
    db_engine: DbEngineResource, archive_dir: ArchiveDirResource
) -> dg.MaterializeResult:
    session_factory = sessionmaker(bind=db_engine.get_engine())

    with session_factory() as session:
        result = archive_pending_trades(session, Path(archive_dir.path))

    return dg.MaterializeResult(
        metadata={
            "archived_count": result.archived_count,
            "archive_path": str(result.archive_path) if result.archive_path else None,
            "uncompressed_bytes": result.uncompressed_bytes,
            "compressed_bytes": result.compressed_bytes,
            "compression_ratio": round(result.compression_ratio, 2),
        }
    )


archival_job = dg.define_asset_job("archival_job", selection=[archived_trades])

archival_schedule = dg.ScheduleDefinition(
    job=archival_job,
    cron_schedule="* * * * *",  # every minute — a demo cadence, not a scale-tuned one
)


def _production_dsn() -> str:
    config = load_config()
    return config.postgres.dsn.replace("+asyncpg", "+psycopg")


defs = dg.Definitions(
    assets=[archived_trades],
    schedules=[archival_schedule],
    resources={
        "db_engine": DbEngineResource(dsn=_production_dsn()),
        "archive_dir": ArchiveDirResource(),
    },
)
