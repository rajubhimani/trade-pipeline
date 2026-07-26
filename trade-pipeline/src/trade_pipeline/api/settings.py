"""API-specific settings: RSA keys + CORS.

Two classes, deliberately not one: ``ApiSettings`` is a plain, trivially
constructible value object holding actual key *content* (not a path) —
tests build one directly with an in-memory-generated ephemeral RSA keypair
(see tests/api/conftest.py), the same dependency-injection pattern used
throughout this codebase (``create_app`` vs ``build_production_app``,
``DbEngineResource`` vs a hardcoded engine). ``ApiEnvSettings`` is the
pydantic-settings class that actually reads the environment/``.env`` file —
only ``load_api_settings()`` (the real production path) touches it.
"""

from dataclasses import dataclass
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_KEYS_DIR = Path(__file__).parent.parent.parent.parent / "keys"


@dataclass(frozen=True, slots=True)
class ApiSettings:
    private_key: str
    public_key: str
    cors_origins: tuple[str, ...]


class ApiEnvSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    jwt_private_key_path: Path = DEFAULT_KEYS_DIR / "private.pem"
    jwt_public_key_path: Path = DEFAULT_KEYS_DIR / "public.pem"
    # Comma-separated — parsed into a tuple by `cors_origins_tuple` below.
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origins_tuple(self) -> tuple[str, ...]:
        return tuple(o.strip() for o in self.cors_origins.split(",") if o.strip())


def load_api_settings() -> ApiSettings:
    env = ApiEnvSettings()
    return ApiSettings(
        private_key=env.jwt_private_key_path.read_text(),
        public_key=env.jwt_public_key_path.read_text(),
        cors_origins=env.cors_origins_tuple,
    )
