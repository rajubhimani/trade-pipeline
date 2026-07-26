import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from trade_pipeline.api.main import create_app
from trade_pipeline.api.settings import ApiSettings


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
async def app(pg_async_engine, redis_client):
    private_key, public_key = _generate_keypair()
    settings = ApiSettings(
        private_key=private_key,
        public_key=public_key,
        cors_origins=("http://localhost:3000",),
    )

    fastapi_app = create_app(
        engine=pg_async_engine, redis_client=redis_client, api_settings=settings
    )
    yield fastapi_app


@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def demo_credentials():
    return {"username": "demo", "password": "trade-pipeline-demo"}
