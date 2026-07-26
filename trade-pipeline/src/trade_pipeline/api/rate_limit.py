"""Rate limiting — pure ASGI middleware, Redis-backed fixed window.

Originally built on ``slowapi``, replaced after its own internals triggered
``DeprecationWarning: asyncio.iscoroutinefunction ... slated for removal in
Python 3.16`` on 3.14 — a real signal the library isn't keeping pace with
current Python, not something we can patch from the outside. This
implementation instead matches the plan's own Week 6-7 system-design
guidance for a rate limiter: "Redis INCR + TTL... atomic check-and-increment"
— and is Redis-backed rather than slowapi's default in-process storage, which
means it works correctly across multiple API worker processes, not just one.

Atomicity note: ``INCR`` on a previously-nonexistent key is what makes this
safe without a Lua script — exactly one concurrent caller will ever observe
the counter transition 0->1, so exactly one caller sets the expiry. No race
window between the increment and the expire.
"""

from redis import Redis
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class RateLimitRule:
    __slots__ = ("limit", "path_prefix", "window_seconds")

    def __init__(self, path_prefix: str, limit: int, window_seconds: int):
        self.path_prefix = path_prefix
        self.limit = limit
        self.window_seconds = window_seconds


class RateLimitMiddleware:
    def __init__(self, app: ASGIApp, redis_client: Redis, rules: list[RateLimitRule]):
        self.app = app
        self.redis = redis_client
        # Longest prefix first, so "/auth/login" matches a more specific rule
        # than a bare "/" catch-all if one is ever added.
        self.rules = sorted(rules, key=lambda r: len(r.path_prefix), reverse=True)

    def _matching_rule(self, path: str) -> RateLimitRule | None:
        for rule in self.rules:
            if path.startswith(rule.path_prefix):
                return rule
        return None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        rule = self._matching_rule(scope["path"])
        if rule is None:
            await self.app(scope, receive, send)
            return

        client = scope.get("client")
        client_ip = client[0] if client else "unknown"
        key = f"ratelimit:{rule.path_prefix}:{client_ip}"

        count = self.redis.incr(key)
        if count == 1:
            self.redis.expire(key, rule.window_seconds)

        if count > rule.limit:
            response = JSONResponse(
                status_code=429,
                content={"detail": "rate limit exceeded"},
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
