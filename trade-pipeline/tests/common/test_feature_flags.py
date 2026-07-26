import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from trade_pipeline.common.db_models import Base
from trade_pipeline.common.feature_flags import is_enabled, set_enabled


@pytest.fixture
async def session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as s:
        yield s
    await engine.dispose()


async def test_flag_with_no_row_defaults_to_false(session):
    assert await is_enabled(session, "enrichment_enabled") is False


async def test_flag_with_no_row_and_no_known_default_is_false(session):
    assert await is_enabled(session, "some_unregistered_flag") is False


async def test_set_enabled_creates_a_row(session):
    await set_enabled(session, "enrichment_enabled", True)
    assert await is_enabled(session, "enrichment_enabled") is True


async def test_set_enabled_updates_an_existing_row(session):
    await set_enabled(session, "enrichment_enabled", True)
    await set_enabled(session, "enrichment_enabled", False)
    assert await is_enabled(session, "enrichment_enabled") is False


async def test_set_enabled_returns_the_current_row(session):
    row = await set_enabled(session, "enrichment_enabled", True)
    assert row.name == "enrichment_enabled"
    assert row.enabled is True
