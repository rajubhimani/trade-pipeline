async def _login(client, demo_credentials) -> str:
    resp = await client.post("/auth/login", json=demo_credentials)
    return resp.json()["access_token"]


async def test_get_unknown_flag_defaults_to_disabled(client, demo_credentials):
    token = await _login(client, demo_credentials)
    resp = await client.get(
        "/admin/feature-flags/enrichment_enabled", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert resp.json() == {"name": "enrichment_enabled", "enabled": False}


async def test_patch_enables_a_flag(client, demo_credentials):
    token = await _login(client, demo_credentials)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.patch(
        "/admin/feature-flags/enrichment_enabled", json={"enabled": True}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json() == {"name": "enrichment_enabled", "enabled": True}

    follow_up = await client.get("/admin/feature-flags/enrichment_enabled", headers=headers)
    assert follow_up.json()["enabled"] is True


async def test_patch_disables_a_previously_enabled_flag(client, demo_credentials):
    token = await _login(client, demo_credentials)
    headers = {"Authorization": f"Bearer {token}"}

    await client.patch(
        "/admin/feature-flags/enrichment_enabled", json={"enabled": True}, headers=headers
    )
    resp = await client.patch(
        "/admin/feature-flags/enrichment_enabled", json={"enabled": False}, headers=headers
    )
    assert resp.json()["enabled"] is False


async def test_admin_endpoints_require_auth(client):
    resp = await client.get("/admin/feature-flags/enrichment_enabled")
    assert resp.status_code == 401
