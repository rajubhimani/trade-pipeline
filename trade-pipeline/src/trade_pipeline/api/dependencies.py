"""FastAPI dependencies — DB session, Redis-backed stores, current-user auth.

Everything reads shared resources off ``request.app.state`` (set up once in
``api/main.py``'s app factory) rather than module-level globals, so tests can
build an app with a SQLite in-memory engine / fake Redis without monkeypatching
anything (see tests/api/conftest.py).
"""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from trade_pipeline.api.auth.blocklist import TokenBlocklist
from trade_pipeline.api.auth.jwt_tokens import TokenError, decode_access_token

_bearer_scheme = HTTPBearer(auto_error=True)


async def get_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    session_factory = request.app.state.async_session_factory
    async with session_factory() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user_id(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer_scheme)],
) -> str:
    settings = request.app.state.api_settings
    blocklist: TokenBlocklist = request.app.state.token_blocklist

    try:
        claims = decode_access_token(credentials.credentials, settings.public_key)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or expired token"
        ) from exc

    if blocklist.is_revoked(claims.jti):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token revoked")

    return claims.sub


CurrentUserDep = Annotated[str, Depends(get_current_user_id)]
