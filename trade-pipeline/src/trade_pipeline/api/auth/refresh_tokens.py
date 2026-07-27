"""Refresh-token store — Redis-backed, single-use, rotated on every refresh.

Deliberately NOT a JWT: a refresh token is a random opaque value whose only
job is "prove you're the same browser that logged in a moment ago" — a JWT's
self-contained-claims property buys nothing here and would need its own
revocation handling anyway. A random UUID looked up in Redis is simpler and
trivially revocable (delete the key).

Rotation-on-use (delete old, issue new) means a stolen-and-replayed refresh
token can be used at most once before the legitimate client's next refresh
fails — which is the detection signal for token theft the plan's Week 3
project track calls for.
"""

from dataclasses import dataclass
from uuid import uuid4

from redis import Redis

REFRESH_TOKEN_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days


class RefreshTokenError(Exception):
    """Raised when a refresh token is missing, expired, or already used."""


@dataclass(frozen=True, slots=True)
class RefreshTokenStore:
    redis: Redis

    def _key(self, token: str) -> str:
        return f"refresh:{token}"

    def issue(self, user_id: str) -> str:
        token = str(uuid4())
        self.redis.set(self._key(token), user_id, ex=REFRESH_TOKEN_TTL_SECONDS)
        return token

    def rotate(self, token: str) -> tuple[str, str]:
        """Validate + consume `token`, returning (user_id, new_token).

        Uses GETDEL so validation and single-use consumption are one atomic
        round trip — no window where two concurrent refreshes could both
        succeed against the same token.
        """
        user_id = self.redis.getdel(self._key(token))
        if user_id is None:
            raise RefreshTokenError("refresh token not found or already used")
        user_id = user_id.decode() if isinstance(user_id, bytes) else user_id
        return user_id, self.issue(user_id)

    def revoke(self, token: str) -> None:
        self.redis.delete(self._key(token))
