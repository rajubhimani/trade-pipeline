"""Alembic environment — resolves its connection from the app's own config
instead of a hardcoded/duplicated URL, and reuses an already-open engine
when one is handed in via ``config.attributes["connection"]`` (see
``common/migrations.py``), so callers that already built an engine
(the consumer's own startup, the one-shot ``migrate`` compose service)
don't open a second connection to Postgres just to run migrations.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from trade_pipeline.common.config import load_config
from trade_pipeline.common.db_models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    # Alembic (via psycopg2/psycopg) is sync-only — the app's default DSN
    # uses the async asyncpg driver for the FastAPI layer, so swap to the
    # sync psycopg driver here, same as scripts/migrate.py and
    # consumer/postgres_sink.make_engine.
    return load_config().postgres.dsn.replace("+asyncpg", "+psycopg")


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    given_engine = config.attributes.get("connection")
    engine = given_engine if given_engine is not None else engine_from_config(
        {"sqlalchemy.url": get_url()},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

    if given_engine is None:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
