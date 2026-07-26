"""JWT access-token encode/decode — RS256 only, pinned explicitly.

Implements the plan's Week 5 JWT hardening checklist:
- Algorithm is always passed explicitly on decode (``algorithms=["RS256"]``);
  never taken from the token header. This is the fix for both the
  ``alg:none`` attack (attacker strips the signature) and the
  RS256->HS256 algorithm-confusion attack (attacker signs with the public
  key, which is public, as if it were an HS256 shared secret) — a server
  that lets the token pick its own algorithm is vulnerable to both.
- Every token gets an explicit ``exp`` and a unique ``jti`` (for the Redis
  revocation blocklist on logout — see ``api/auth/blocklist.py``).
- Refresh tokens are NOT JWTs — see ``api/auth/refresh_tokens.py``. Only the
  short-lived access token is a JWT here.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt

ALGORITHM = "RS256"
ACCESS_TOKEN_TTL = timedelta(minutes=15)


class TokenError(Exception):
    """Raised for any invalid/expired/malformed/blocklisted token."""


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    sub: str  # user id
    jti: str  # unique token id, used for the revocation blocklist
    exp: datetime


def issue_access_token(user_id: str, private_key: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "jti": str(uuid4()),
        "iat": now,
        "exp": now + ACCESS_TOKEN_TTL,
    }
    return jwt.encode(payload, private_key, algorithm=ALGORITHM)


def decode_access_token(token: str, public_key: str) -> AccessTokenClaims:
    try:
        payload = jwt.decode(
            token,
            public_key,
            algorithms=[ALGORITHM],  # pinned — never read the alg from the token header
            options={"require": ["exp", "jti", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError("invalid token") from exc

    return AccessTokenClaims(
        sub=payload["sub"],
        jti=payload["jti"],
        exp=datetime.fromtimestamp(payload["exp"], tz=UTC),
    )
