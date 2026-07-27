"""create_app()'s dashboard static-mount, using the injectable
`dashboard_static_dir` parameter (api/main.py) rather than depending on
whether `npm run build` has actually been run in dashboard/ on this machine
— deterministic either way, and exercises both branches (mounted / absent).
"""

from httpx import ASGITransport, AsyncClient

from trade_pipeline.api.main import create_app


async def test_dashboard_mounted_when_static_dir_exists(
    pg_async_engine, redis_client, tmp_path
):
    from trade_pipeline.api.settings import ApiSettings

    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<html>dashboard</html>")

    app = create_app(
        engine=pg_async_engine,
        redis_client=redis_client,
        api_settings=ApiSettings(private_key="", public_key="", cors_origins=()),
        dashboard_static_dir=static_dir,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/dashboard/")

    assert response.status_code == 200
    assert response.text == "<html>dashboard</html>"


async def test_dashboard_not_mounted_when_static_dir_absent(
    pg_async_engine, redis_client, tmp_path
):
    from trade_pipeline.api.settings import ApiSettings

    app = create_app(
        engine=pg_async_engine,
        redis_client=redis_client,
        api_settings=ApiSettings(private_key="", public_key="", cors_origins=()),
        dashboard_static_dir=tmp_path / "does-not-exist",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/dashboard/")

    assert response.status_code == 404
