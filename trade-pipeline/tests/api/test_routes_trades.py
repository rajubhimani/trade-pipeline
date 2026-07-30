from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import insert

from trade_pipeline.common.db_models import FeatureFlag, Trade


async def _seed_trade(app, **overrides):
    defaults = {
        "broker_id": "broker-1",
        "trade_id": "t-1",
        "symbol": "AAPL",
        "qty": 10,
        "price": Decimal("190.50"),
        "timestamp": datetime(2026, 7, 26, tzinfo=UTC),
    }
    defaults.update(overrides)
    session_factory = app.state.async_session_factory
    async with session_factory() as session:
        await session.execute(insert(Trade).values(**defaults))
        await session.commit()


async def _login(client, demo_credentials) -> str:
    resp = await client.post("/auth/login", json=demo_credentials)
    return resp.json()["access_token"]


async def test_trades_without_token_returns_401(client):
    resp = await client.get("/trades")
    assert resp.status_code == 401


async def test_trades_with_valid_token_returns_seeded_rows(app, client, demo_credentials):
    await _seed_trade(app, trade_id="t-1", symbol="AAPL")
    await _seed_trade(app, trade_id="t-2", symbol="MSFT")

    token = await _login(client, demo_credentials)
    resp = await client.get("/trades", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    trade_ids = {row["trade_id"] for row in resp.json()}
    assert trade_ids == {"t-1", "t-2"}


async def test_trades_filters_by_symbol(app, client, demo_credentials):
    await _seed_trade(app, trade_id="t-1", symbol="AAPL")
    await _seed_trade(app, trade_id="t-2", symbol="MSFT")

    token = await _login(client, demo_credentials)
    resp = await client.get(
        "/trades", params={"symbol": "MSFT"}, headers={"Authorization": f"Bearer {token}"}
    )

    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["symbol"] == "MSFT"


async def test_trades_respects_limit(app, client, demo_credentials):
    for i in range(5):
        await _seed_trade(app, trade_id=f"t-{i}")

    token = await _login(client, demo_credentials)
    resp = await client.get(
        "/trades", params={"limit": 2}, headers={"Authorization": f"Bearer {token}"}
    )

    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_enrichment_is_null_when_flag_disabled(app, client, demo_credentials):
    await _seed_trade(
        app,
        trade_id="t-1",
        enrichment={"risk_score": {"data": {"score": 17}, "error": None}},
        enrichment_status="completed",
    )
    token = await _login(client, demo_credentials)

    resp = await client.get("/trades", headers={"Authorization": f"Bearer {token}"})

    row = resp.json()[0]
    assert row["enrichment"] is None
    assert row["enrichment_status"] == "disabled"


async def test_enrichment_is_read_from_stored_column_when_flag_enabled_via_admin_api(
    app, client, demo_credentials
):
    """GET /trades must never call Temporal or an enrichment service itself
    — it only reads whatever the Temporal worker already persisted (see
    routes_trades.py's module docstring). Seed the stored result directly
    rather than exercising the workflow, so this test also proves the
    endpoint doesn't recompute anything of its own.
    """
    stored = {
        "risk_score": {"data": {"score": 17, "trade_id": "t-1"}, "error": None},
        "sentiment": {"data": None, "error": "EnrichmentTimeoutError"},
    }
    await _seed_trade(
        app, trade_id="t-1", enrichment=stored, enrichment_status="completed_with_errors"
    )
    token = await _login(client, demo_credentials)
    headers = {"Authorization": f"Bearer {token}"}

    await client.patch(
        "/admin/feature-flags/enrichment_enabled", json={"enabled": True}, headers=headers
    )
    resp = await client.get("/trades", headers=headers)

    row = resp.json()[0]
    assert row["enrichment"] == stored
    assert row["enrichment_status"] == "completed_with_errors"


async def test_enrichment_differs_per_trade(app, client, demo_credentials):
    await _seed_trade(
        app,
        trade_id="t-1",
        enrichment={"risk_score": {"data": {"score": 1}, "error": None}},
        enrichment_status="completed",
    )
    await _seed_trade(
        app,
        trade_id="t-2",
        enrichment={"risk_score": {"data": {"score": 2}, "error": None}},
        enrichment_status="completed",
    )
    token = await _login(client, demo_credentials)
    headers = {"Authorization": f"Bearer {token}"}
    await client.patch(
        "/admin/feature-flags/enrichment_enabled", json={"enabled": True}, headers=headers
    )

    resp = await client.get("/trades", headers=headers)
    by_trade_id = {row["trade_id"]: row["enrichment"] for row in resp.json()}

    assert by_trade_id["t-1"]["risk_score"]["data"] == {"score": 1}
    assert by_trade_id["t-2"]["risk_score"]["data"] == {"score": 2}


async def test_pending_enrichment_status_returned_without_calling_services(
    app, client, demo_credentials
):
    await _seed_trade(app, trade_id="t-1", enrichment=None, enrichment_status="pending")
    token = await _login(client, demo_credentials)
    headers = {"Authorization": f"Bearer {token}"}
    await client.patch(
        "/admin/feature-flags/enrichment_enabled", json={"enabled": True}, headers=headers
    )

    resp = await client.get("/trades", headers=headers)

    row = resp.json()[0]
    assert row["enrichment"] is None
    assert row["enrichment_status"] == "pending"


async def test_enrichment_reflects_a_direct_db_row_update(app, client, demo_credentials):
    """The feature_flags table is the actual source of truth — flipping it
    with a direct DB write (no admin API call) must take effect on the very
    next request, same as it would for an operator running raw SQL.
    """
    await _seed_trade(
        app,
        trade_id="t-1",
        enrichment={"risk_score": {"data": {"score": 5}, "error": None}},
        enrichment_status="completed",
    )
    token = await _login(client, demo_credentials)
    headers = {"Authorization": f"Bearer {token}"}

    session_factory = app.state.async_session_factory
    async with session_factory() as session:
        session.add(FeatureFlag(name="enrichment_enabled", enabled=True))
        await session.commit()

    resp = await client.get("/trades", headers=headers)
    assert resp.json()[0]["enrichment"] is not None
