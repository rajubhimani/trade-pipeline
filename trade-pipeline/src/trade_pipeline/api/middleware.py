"""Security headers + audit logging — implemented as pure ASGI middleware.

Deliberately NOT ``starlette.middleware.base.BaseHTTPMiddleware`` (the
tutorial-standard choice): confirmed via current research that
``BaseHTTPMiddleware`` wraps every request in an extra response-streaming
layer that measurably costs throughput (~1.8x versus pure ASGI) and has known
rough edges with ``contextvars``/background-task propagation, because it runs
the inner app in a separate anyio task. For header injection (cheap, no I/O)
and audit logging (also cheap), plain ASGI middleware avoids both costs
entirely — worth doing here since these run on every single request. See
docs/DECISIONS.md.
"""

import time

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = structlog.get_logger()

_SECURITY_HEADERS = {
    b"x-content-type-options": b"nosniff",
    b"x-frame-options": b"DENY",
    b"strict-transport-security": b"max-age=63072000; includeSubDomains",
    b"content-security-policy": b"default-src 'self'",
    b"referrer-policy": b"strict-origin-when-cross-origin",
}

# FastAPI's auto-generated /docs and /redoc pages load Swagger UI/Redoc's
# JS+CSS from a CDN and run an inline <script> to initialize it — both
# blocked outright by the strict `default-src 'self'` CSP above (no
# 'unsafe-inline', no CDN origin allowed), which renders the page as a
# blank `<div id="swagger-ui">` with no visible error (confirmed: the HTML
# itself loads fine, the browser just silently refuses the CSP-violating
# script/style). These are FastAPI's own introspection/dev-docs endpoints,
# not part of the hardened application surface, so they're excluded from
# the strict policy rather than weakening it (e.g. adding 'unsafe-inline')
# for every real endpoint just to accommodate the docs UI.
_UNRESTRICTED_CSP_PATHS = frozenset({"/docs", "/redoc"})


class SecurityHeadersMiddleware:
    """Adds a fixed set of security headers to every HTTP response."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers_to_add = _SECURITY_HEADERS
        if scope["path"] in _UNRESTRICTED_CSP_PATHS:
            headers_to_add = {
                k: v for k, v in _SECURITY_HEADERS.items() if k != b"content-security-policy"
            }

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(headers_to_add.items())
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)


class AuditLogMiddleware:
    """Structured audit log for every request under /auth/*.

    Logs after the response is known (status code included) so a single log
    line captures the full outcome — not split across a "request started" and
    "request finished" pair, which is more useful for scanning brute-force
    attempts (many failed logins from one IP) after the fact.
    """

    def __init__(self, app: ASGIApp, audited_prefix: str = "/auth") -> None:
        self.app = app
        self.audited_prefix = audited_prefix

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith(self.audited_prefix):
            await self.app(scope, receive, send)
            return

        status_holder: dict[str, int] = {}
        start = time.monotonic()

        async def send_and_capture(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
            await send(message)

        await self.app(scope, receive, send_and_capture)

        client = scope.get("client")
        headers = dict(scope.get("headers", []))
        logger.info(
            "auth_event",
            path=scope["path"],
            method=scope["method"],
            status=status_holder.get("status"),
            ip=client[0] if client else None,
            user_agent=headers.get(b"user-agent", b"").decode(errors="replace"),
            duration_ms=round((time.monotonic() - start) * 1000, 2),
        )
