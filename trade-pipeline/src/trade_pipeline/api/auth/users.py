"""Minimal demo user store — NOT a real user system.

Scope cut, documented explicitly: this project's focus is the pipeline and
its security hardening (JWT, headers, rate limiting), not building a full
user-registration/management system, which is out of scope per
docs/features/fastapi-query-layer.md. One hardcoded demo account is enough to
exercise the whole auth flow end to end.

Password hashing uses Argon2id (via ``argon2-cffi``), the current
OWASP-recommended default for new applications — chosen over bcrypt after
checking current guidance (see docs/DECISIONS.md); bcrypt is still fine but
no longer the default recommendation, and Argon2id's PasswordHasher API
already handles its own re-hash-on-parameter-change bookkeeping.
"""

from dataclasses import dataclass

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher()


@dataclass(frozen=True, slots=True)
class User:
    user_id: str
    username: str
    password_hash: str


def _demo_users() -> dict[str, User]:
    # Fixed demo credentials: username "demo", password "trade-pipeline-demo".
    # Never do this in a real system — this exists purely so the auth flow
    # (login/refresh/logout) has something to authenticate against.
    return {
        "demo": User(
            user_id="user-demo",
            username="demo",
            password_hash=_hasher.hash("trade-pipeline-demo"),
        )
    }


_USERS = _demo_users()


def authenticate(username: str, password: str) -> User | None:
    user = _USERS.get(username)
    if user is None:
        return None
    try:
        _hasher.verify(user.password_hash, password)
    except VerifyMismatchError:
        return None
    return user
