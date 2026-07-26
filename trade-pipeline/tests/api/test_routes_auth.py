async def test_login_with_valid_credentials_returns_access_token(client, demo_credentials):
    resp = await client.post("/auth/login", json=demo_credentials)
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert "refresh_token" in resp.cookies


async def test_login_with_wrong_password_returns_401(client):
    resp = await client.post(
        "/auth/login", json={"username": "demo", "password": "wrong-password"}
    )
    assert resp.status_code == 401


async def test_login_with_unknown_user_returns_401(client):
    resp = await client.post(
        "/auth/login", json={"username": "nobody", "password": "whatever"}
    )
    assert resp.status_code == 401


async def test_refresh_without_cookie_returns_401(client):
    resp = await client.post("/auth/refresh")
    assert resp.status_code == 401


async def test_refresh_rotates_token_and_old_one_stops_working(client, demo_credentials):
    login_resp = await client.post("/auth/login", json=demo_credentials)
    old_refresh_cookie = login_resp.cookies["refresh_token"]

    # httpx deprecated per-request `cookies=` in favor of setting them on the
    # client instance — do that instead of passing cookies per call.
    client.cookies.set("refresh_token", old_refresh_cookie)
    refresh_resp = await client.post("/auth/refresh")
    assert refresh_resp.status_code == 200
    assert refresh_resp.json()["access_token"]

    # Old refresh token is single-use — reusing it must now fail. The client
    # auto-updated its cookie jar from the refresh response's Set-Cookie, so
    # force the old value back to actually test reuse.
    client.cookies.set("refresh_token", old_refresh_cookie)
    reuse_resp = await client.post("/auth/refresh")
    assert reuse_resp.status_code == 401


async def test_logout_revokes_access_token(client, demo_credentials):
    login_resp = await client.post("/auth/login", json=demo_credentials)
    access_token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    logout_resp = await client.post("/auth/logout", headers=headers)
    assert logout_resp.status_code == 204

    # The now-revoked access token must be rejected on the next protected call.
    trades_resp = await client.get("/trades", headers=headers)
    assert trades_resp.status_code == 401
