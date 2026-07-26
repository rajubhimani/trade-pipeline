"""Auth routes: login, refresh, logout.

Refresh token travels as an httpOnly cookie (JS can't read it, mitigating
XSS-based theft) — access token is returned in the response body for the
client to send as a Bearer header, per the plan's Week 3 project track.
"""

from typing import Annotated

from fastapi import APIRouter, Cookie, HTTPException, Request, Response, status

from trade_pipeline.api.auth.jwt_tokens import (
    TokenError,
    decode_access_token,
    issue_access_token,
)
from trade_pipeline.api.auth.refresh_tokens import RefreshTokenError
from trade_pipeline.api.auth.users import authenticate
from trade_pipeline.api.dependencies import CurrentUserDep
from trade_pipeline.api.schemas import LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE_MAX_AGE = 7 * 24 * 60 * 60


@router.post("/login", response_model=TokenResponse)
async def login(request: Request, body: LoginRequest, response: Response) -> TokenResponse:
    user = authenticate(body.username, body.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")

    settings = request.app.state.api_settings
    access_token = issue_access_token(user.user_id, settings.private_key)

    refresh_store = request.app.state.refresh_token_store
    refresh_token = refresh_store.issue(user.user_id)
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        refresh_token,
        max_age=REFRESH_COOKIE_MAX_AGE,
        httponly=True,
        samesite="strict",
    )

    return TokenResponse(access_token=access_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE_NAME)] = None,
) -> TokenResponse:
    if refresh_token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="no refresh token")

    refresh_store = request.app.state.refresh_token_store
    try:
        user_id, new_refresh_token = refresh_store.rotate(refresh_token)
    except RefreshTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid refresh token"
        ) from exc

    settings = request.app.state.api_settings
    access_token = issue_access_token(user_id, settings.private_key)

    response.set_cookie(
        REFRESH_COOKIE_NAME,
        new_refresh_token,
        max_age=REFRESH_COOKIE_MAX_AGE,
        httponly=True,
        samesite="strict",
    )
    return TokenResponse(access_token=access_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE_NAME)] = None,
) -> None:
    # current_user's auth dependency already validated the access token;
    # re-decode here only to get its jti/exp for the blocklist entry.
    auth_header = request.headers.get("authorization", "")
    token = auth_header.removeprefix("Bearer ").strip()
    settings = request.app.state.api_settings
    try:
        claims = decode_access_token(token, settings.public_key)
        request.app.state.token_blocklist.revoke(claims.jti, claims.exp)
    except TokenError:
        pass  # already invalid/expired — nothing to revoke

    if refresh_token is not None:
        request.app.state.refresh_token_store.revoke(refresh_token)

    response.delete_cookie(REFRESH_COOKIE_NAME)
