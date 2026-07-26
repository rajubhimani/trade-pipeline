"""API-specific settings: RSA keys + Redis/DB connections.

Kept separate from ``common/config.py`` (which covers Kafka/Redis/Postgres
connection info shared with the producer/consumer) because the API process
additionally needs the RS256 keypair, which the producer/consumer never
touch.
"""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ApiSettings:
    private_key: str
    public_key: str
    cors_origins: tuple[str, ...]


def load_api_settings(keys_dir: Path | None = None) -> ApiSettings:
    keys_dir = keys_dir or Path(__file__).parent.parent.parent.parent / "keys"
    private_key_path = Path(os.environ.get("JWT_PRIVATE_KEY_PATH", keys_dir / "private.pem"))
    public_key_path = Path(os.environ.get("JWT_PUBLIC_KEY_PATH", keys_dir / "public.pem"))

    cors_origins_env = os.environ.get("CORS_ORIGINS", "http://localhost:3000")
    cors_origins = tuple(o.strip() for o in cors_origins_env.split(",") if o.strip())

    return ApiSettings(
        private_key=private_key_path.read_text(),
        public_key=public_key_path.read_text(),
        cors_origins=cors_origins,
    )
