"""SecurityHeadersMiddleware — in particular the /docs & /redoc CSP carve-out
(see middleware.py's module comment: FastAPI's default Swagger UI page loads
CDN assets + runs an inline <script>, both blocked outright by the strict
`default-src 'self'` policy applied everywhere else, which silently renders
/docs as a blank page rather than an obvious error).
"""


async def test_normal_routes_get_the_strict_csp(client):
    response = await client.get("/trades")  # 401 without auth, headers still apply

    assert response.headers["content-security-policy"] == "default-src 'self'"
    assert response.headers["x-content-type-options"] == "nosniff"


async def test_docs_page_has_no_csp_header(client):
    response = await client.get("/docs")

    assert "content-security-policy" not in response.headers
    # Other security headers still apply — only CSP is carved out.
    assert response.headers["x-content-type-options"] == "nosniff"


async def test_redoc_page_has_no_csp_header(client):
    response = await client.get("/redoc")

    assert "content-security-policy" not in response.headers
