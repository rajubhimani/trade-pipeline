"""Access-token revocation blocklist — Redis-backed, keyed by JWT `jti`.

JWTs are stateless by design, which means they can't be individually
invalidated once issued — the only way to revoke one before it naturally
expires is an external "is this one dead" check. Storing the `jti` with a TTL
equal to the token's remaining lifetime keeps the blocklist self-cleaning
(nothing to prune — Redis expires the key on its own once the token would
have expired anyway).
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from redis import Redis


@dataclass(frozen=True, slots=True)
class TokenBlocklist:
    redis: Redis

    def _key(self, jti: str) -> str:
        return f"blocklist:{jti}"

    def revoke(self, jti: str, expires_at: datetime) -> None:
        ttl_seconds = max(1, int((expires_at - datetime.now(UTC)).total_seconds()))
        self.redis.set(self._key(jti), 1, ex=ttl_seconds)

    def is_revoked(self, jti: str) -> bool:
        return self.redis.exists(self._key(jti)) > 0
