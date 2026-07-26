"""FastAPI app factory.

A factory (``create_app``) rather than a single module-level ``app`` so tests
can inject a SQLite in-memory engine / fake Redis instead of the real
Postgres/Redis connections (see tests/api/conftest.py) — nothing here reaches
for a module-level global.
"""

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from redis import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from trade_pipeline.api.auth.blocklist import TokenBlocklist
from trade_pipeline.api.auth.refresh_tokens import RefreshTokenStore
from trade_pipeline.api.middleware import AuditLogMiddleware, SecurityHeadersMiddleware
from trade_pipeline.api.rate_limit import RateLimitMiddleware, RateLimitRule
from trade_pipeline.api.routes_auth import router as auth_router
from trade_pipeline.api.routes_trades import router as trades_router
from trade_pipeline.api.settings import ApiSettings

logger = structlog.get_logger()


async def _global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled_exception", exc=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "internal server error"},
    )


async def _validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    # Default FastAPI 422 responses echo back field names/types/values, which
    # helps an attacker map the API's internal shape. Log the detail, return
    # nothing more specific to the client than "invalid request".
    logger.info("validation_error", detail=exc.errors(), path=request.url.path)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "invalid request"},
    )


def create_app(
    engine: AsyncEngine,
    redis_client: Redis,
    api_settings: ApiSettings,
) -> FastAPI:
    app = FastAPI(title="trade-pipeline")

    app.state.async_session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    app.state.api_settings = api_settings
    app.state.token_blocklist = TokenBlocklist(redis_client)
    app.state.refresh_token_store = RefreshTokenStore(redis_client)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(api_settings.cors_origins),
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
        allow_credentials=True,
    )
    app.add_middleware(AuditLogMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    # Stricter limit on auth endpoints than data reads, to slow brute force.
    app.add_middleware(
        RateLimitMiddleware,
        redis_client=redis_client,
        rules=[
            RateLimitRule(path_prefix="/auth", limit=10, window_seconds=60),
            RateLimitRule(path_prefix="/trades", limit=100, window_seconds=60),
        ],
    )

    app.add_exception_handler(RequestValidationError, _validation_exception_handler)
    app.add_exception_handler(Exception, _global_exception_handler)

    app.include_router(auth_router)
    app.include_router(trades_router)

    Instrumentator().instrument(app).expose(app)

    return app
