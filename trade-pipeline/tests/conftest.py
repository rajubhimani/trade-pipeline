"""Shared real-service fixtures — Postgres and Redis via Docker, no
SQLite/fakeredis. Connects to the services this project's own
docker-compose.yml already provides (`docker compose up -d` before running
tests). Every DB/Redis-touching test in this suite goes through real
services now, not in-memory substitutes — see docs/DECISIONS.md
"Real Postgres/Redis in tests, not SQLite/fakeredis".

Each pytest-xdist worker gets its own Postgres schema (via `search_path`)
and its own Redis logical DB index, both derived from the worker id, so
`pytest -n auto` can run safely in parallel against the same shared
containers without workers stomping on each other's data. Within a single
worker, each test gets a clean slate via table truncation / FLUSHDB in the
fixture itself — no cross-test leakage either.
"""

import os
import re

import pytest
import pytest_asyncio
from redis import Redis
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from trade_pipeline.common.db_models import Base
from trade_pipeline.common.migrations import upgrade_to_head
from trade_pipeline.common.partitioning import ensure_partitions

POSTGRES_DSN = os.environ.get(
    "TEST_POSTGRES_DSN",
    "postgresql+psycopg://trade_pipeline:trade_pipeline@localhost:5432/trade_pipeline",
)
POSTGRES_ASYNC_DSN = os.environ.get(
    "TEST_POSTGRES_ASYNC_DSN",
    "postgresql+asyncpg://trade_pipeline:trade_pipeline@localhost:5432/trade_pipeline",
)
REDIS_URL = os.environ.get("TEST_REDIS_URL", "redis://localhost:6379")


def _worker_index() -> int:
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "gw0")
    match = re.search(r"\d+", worker_id)
    return int(match.group()) if match else 0


@pytest.fixture(scope="session")
def worker_schema() -> str:
    return f"test_worker_{_worker_index()}"


@pytest.fixture(scope="session", autouse=True)
def _prepare_worker_schema(worker_schema):
    """Create this worker's schema once per session; drop it at the end so
    repeated local test runs don't accumulate orphaned schemas.
    """
    engine = create_engine(POSTGRES_DSN)
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{worker_schema}"'))
    engine.dispose()
    yield
    engine = create_engine(POSTGRES_DSN)
    with engine.begin() as conn:
        conn.execute(text(f'DROP SCHEMA IF EXISTS "{worker_schema}" CASCADE'))
    engine.dispose()


@pytest.fixture
def pg_engine(worker_schema):
    """Sync engine (psycopg), isolated to this worker's Postgres schema,
    fresh schema (tables dropped + recreated) for every test.
    """
    engine = create_engine(
        POSTGRES_DSN, connect_args={"options": f"-csearch_path={worker_schema}"}
    )
    # Reset to a blank schema (drop_all only knows about Base's own tables,
    # not `alembic_version` — drop it explicitly too, otherwise Alembic
    # thinks it's already at head and skips recreating the tables drop_all
    # just removed).
    Base.metadata.drop_all(engine)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
    # Schema itself comes entirely from Alembic now, same as production
    # (see common/migrations.upgrade_to_head) — no separate create_all path
    # for tests to drift out of sync with.
    upgrade_to_head(engine)
    ensure_partitions(engine)
    yield engine
    engine.dispose()


@pytest_asyncio.fixture
async def pg_async_engine(worker_schema, pg_engine):
    """Async engine (asyncpg), same worker schema as `pg_engine` — a test
    that seeds data with the sync engine and reads it via the async engine
    (or vice versa) sees the same tables. Depends on `pg_engine` purely so
    schema setup (drop/create/partitions) happens before any async test
    runs, without every async test needing to also request `pg_engine`
    itself.
    """
    engine = create_async_engine(
        POSTGRES_ASYNC_DSN,
        connect_args={"server_settings": {"search_path": worker_schema}},
    )
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def pg_async_session(pg_async_engine) -> AsyncSession:
    session_factory = sessionmaker(
        bind=pg_async_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session


@pytest.fixture
def redis_client():
    """Real Redis, isolated to this worker's own logical DB index, flushed
    before every test so no state leaks between tests in the same worker.

    A generous socket_timeout (default is unlimited but individual reads can
    still hit the OS-level default) guards against transient slowness on a
    busy dev machine running many unrelated Docker containers alongside this
    project's own — observed once under -n auto load, not reproducible on a
    dedicated CI runner, but cheap to harden against regardless.
    """
    client = Redis.from_url(REDIS_URL, db=_worker_index(), socket_timeout=10)
    client.flushdb()
    yield client
    client.flushdb()
    client.close()
