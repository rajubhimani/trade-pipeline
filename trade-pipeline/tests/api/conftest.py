import pytest
import pytest_asyncio
from fakeredis import FakeRedis
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from trade_pipeline.api.main import create_app
from trade_pipeline.api.settings import ApiSettings
from trade_pipeline.common.db_models import Base


def _generate_keypair() -> tuple[str, str]:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return private_pem, public_pem


@pytest_asyncio.fixture
async def app():
    # StaticPool: keeps one shared SQLite in-memory connection across the
    # whole engine, so multiple sessions (e.g. one per request) see the same
    # tables — default pooling gives each connection its own independent
    # in-memory DB, which looks like "no such table" errors otherwise.
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    private_key, public_key = _generate_keypair()
    settings = ApiSettings(
        private_key=private_key,
        public_key=public_key,
        cors_origins=("http://localhost:3000",),
    )

    # A fresh FakeRedis per test avoids rate-limit counters leaking between tests.
    redis_client = FakeRedis()

    fastapi_app = create_app(engine=engine, redis_client=redis_client, api_settings=settings)
    fastapi_app.state.test_engine = engine  # kept alive for the test's duration
    yield fastapi_app

    await engine.dispose()


@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def demo_credentials():
    return {"username": "demo", "password": "trade-pipeline-demo"}
