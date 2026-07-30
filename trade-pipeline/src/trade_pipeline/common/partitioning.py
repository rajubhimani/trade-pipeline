"""Postgres range partitioning for the `trades` table.

Answers a direct question during this project's build: "should we partition
Postgres?" Yes, for an append-heavy time-series table like `trades` — see
docs/features/postgres-partitioning.md for the full rationale.

`Trade.__table_args__` (common/db_models.py) declares
`postgresql_partition_by="RANGE (timestamp)"`, so the Alembic migration that
creates the `trades` table (migrations/versions/0001_initial_schema.py)
already emits the correct `PARTITION BY RANGE` parent table DDL. What a
migration can't do — it's a one-time static revision — is create the actual
child partitions on a rolling basis: this module does that instead, at
runtime, every startup: a DEFAULT catch-all partition (without one, an
insert whose timestamp doesn't fall in any explicit range is rejected
outright) plus explicit monthly partitions for the current and next month.

Verified against a live `postgres:18.4-alpine` container (this project's own
docker-compose service) — see docs/features/postgres-partitioning.md.
"""

from datetime import date

from sqlalchemy import Engine, text

TABLE_NAME = "trades"


def ensure_partitions(engine: Engine) -> None:
    """Idempotent: safe to call on every startup. Creates the DEFAULT
    partition plus the current and next month's explicit partitions.
    """
    with engine.begin() as conn:
        conn.execute(
            text(f"""
                CREATE TABLE IF NOT EXISTS {TABLE_NAME}_default
                PARTITION OF {TABLE_NAME} DEFAULT
            """)
        )

    today = date.today()
    ensure_monthly_partition(engine, today.year, today.month)
    next_month_year, next_month = (
        (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
    )
    ensure_monthly_partition(engine, next_month_year, next_month)


def ensure_monthly_partition(engine: Engine, year: int, month: int) -> str:
    """Create (if missing) the partition covering one calendar month.
    Returns the partition's table name.
    """
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    partition_name = f"{TABLE_NAME}_{year:04d}_{month:02d}"

    # Postgres DDL (CREATE TABLE ... PARTITION OF ... FOR VALUES) does not
    # accept bind parameters — confirmed against a live Postgres container
    # ("there is no parameter $1"), not assumed. Safe to inline here since
    # start/end are `date` objects this function constructs itself, never
    # user input.
    with engine.begin() as conn:
        conn.execute(
            text(f"""
                CREATE TABLE IF NOT EXISTS {partition_name}
                PARTITION OF {TABLE_NAME}
                FOR VALUES FROM ('{start.isoformat()}') TO ('{end.isoformat()}')
            """)
        )
    return partition_name


def list_partitions(engine: Engine) -> list[str]:
    """Introspect actual child partitions via Postgres's own catalog —
    proof the parent table really is partitioned, not just named like it is.
    """
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT child.relname
                FROM pg_inherits
                JOIN pg_class parent ON pg_inherits.inhparent = parent.oid
                JOIN pg_class child ON pg_inherits.inhrelid = child.oid
                WHERE parent.relname = :parent
                ORDER BY child.relname
            """),
            {"parent": TABLE_NAME},
        )
        return [row[0] for row in rows]


__all__ = ["TABLE_NAME", "ensure_monthly_partition", "ensure_partitions", "list_partitions"]
