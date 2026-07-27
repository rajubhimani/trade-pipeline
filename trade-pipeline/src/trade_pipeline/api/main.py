"""FastAPI app factory.

A factory (``create_app``) rather than a single module-level ``app`` so tests
can inject a SQLite in-memory engine / fake Redis instead of the real
Postgres/Redis connections (see tests/api/conftest.py) — nothing here reaches
for a module-level global.
"""

from pathlib import Path

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator
from redis import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from trade_pipeline.api.auth.blocklist import TokenBlocklist
from trade_pipeline.api.auth.refresh_tokens import RefreshTokenStore
from trade_pipeline.api.middleware import AuditLogMiddleware, SecurityHeadersMiddleware
from trade_pipeline.api.rate_limit import RateLimitMiddleware, RateLimitRule
from trade_pipeline.api.routes_admin import router as admin_router
from trade_pipeline.api.routes_auth import router as auth_router
from trade_pipeline.api.routes_trades import router as trades_router
from trade_pipeline.api.settings import ApiSettings
from trade_pipeline.enrichment.circuit_breaker import CircuitBreaker
from trade_pipeline.enrichment.mock_services import always_succeeds

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
    dashboard_static_dir: Path | None = None,
) -> FastAPI:
    app = FastAPI(title="trade-pipeline")

    app.state.async_session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    app.state.api_settings = api_settings
    app.state.token_blocklist = TokenBlocklist(redis_client)
    app.state.refresh_token_store = RefreshTokenStore(redis_client)

    # Demo enrichment services for the "enrichment_enabled" feature flag
    # (common/feature_flags.py) — fake data, not a real integration; see
    # docs/features/async-enrichment.md for scope. Kept on app.state, not
    # created fresh per request, so circuit-breaker failure state persists
    # across requests the way it would need to in a real deployment.
    app.state.enrichment_services = {
        "risk_score": always_succeeds({"score": 42}).run,
        "sentiment": always_succeeds({"index": "neutral"}).run,
    }
    app.state.enrichment_breakers = {
        name: CircuitBreaker() for name in app.state.enrichment_services
    }

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
    app.include_router(admin_router)

    Instrumentator().instrument(app).expose(app)

    # Built by `npm run build` in dashboard/ (see dashboard/vite.config.js —
    # outDir points here, base is "/dashboard/" so asset references resolve
    # correctly once mounted at this path). html=True serves index.html for
    # the bare /dashboard path, not just /dashboard/index.html directly.
    # Mounted last: StaticFiles' catch-all shouldn't shadow any API route.
    # Injectable (defaults to the real build output path) so tests can point
    # at a controlled tmp directory instead of depending on whether the
    # dashboard happens to be built locally — same DI pattern as engine/
    # redis_client/api_settings above.
    static_dir = dashboard_static_dir or (Path(__file__).parent / "static")
    if static_dir.exists():
        app.mount("/dashboard", StaticFiles(directory=static_dir, html=True), name="dashboard")

    return app


def build_production_app() -> FastAPI:
    """Zero-arg factory for `uvicorn --factory`, assembling real dependencies
    from config/env rather than the test-injected ones `create_app` takes
    directly. Kept separate from `create_app` itself so the factory/DI shape
    that makes testing easy (see module docstring) isn't compromised by also
    trying to double as the production entrypoint.
    """
    from sqlalchemy.ext.asyncio import create_async_engine

    from trade_pipeline.api.settings import load_api_settings
    from trade_pipeline.common.config import load_config

    config = load_config()
    engine = create_async_engine(config.postgres.dsn)
    redis_client = Redis.from_url(config.redis.url)
    api_settings = load_api_settings()

    return create_app(engine=engine, redis_client=redis_client, api_settings=api_settings)
