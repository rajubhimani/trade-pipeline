from trade_pipeline.common.feature_flags import is_enabled, set_enabled


async def test_flag_with_no_row_defaults_to_false(pg_async_session):
    assert await is_enabled(pg_async_session, "enrichment_enabled") is False


async def test_flag_with_no_row_and_no_known_default_is_false(pg_async_session):
    assert await is_enabled(pg_async_session, "some_unregistered_flag") is False


async def test_set_enabled_creates_a_row(pg_async_session):
    await set_enabled(pg_async_session, "enrichment_enabled", True)
    assert await is_enabled(pg_async_session, "enrichment_enabled") is True


async def test_set_enabled_updates_an_existing_row(pg_async_session):
    await set_enabled(pg_async_session, "enrichment_enabled", True)
    await set_enabled(pg_async_session, "enrichment_enabled", False)
    assert await is_enabled(pg_async_session, "enrichment_enabled") is False


async def test_set_enabled_returns_the_current_row(pg_async_session):
    row = await set_enabled(pg_async_session, "enrichment_enabled", True)
    assert row.name == "enrichment_enabled"
    assert row.enabled is True
