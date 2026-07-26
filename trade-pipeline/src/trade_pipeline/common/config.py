"""App configuration — pydantic-settings, not hand-rolled env parsing.

Precedence (pydantic-settings' own default): real environment variables win
over a `.env` file, which wins over the baked-in defaults below. Locally,
copy `.env.example` to `.env` and edit as needed; in production, real env
vars set by the deployment environment are what actually take effect — no
code change needed to support either.

Every default matches this project's own docker-compose.yml, so `AppConfig()`
with zero configuration works out of the box against `docker compose up -d`.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class KafkaSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KAFKA_", env_file=".env", extra="ignore")

    bootstrap_servers: str = "localhost:9092"
    topic: str = "trades"


class RedisSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REDIS_", env_file=".env", extra="ignore")

    url: str = "redis://localhost:6379/0"
    dedup_ttl_seconds: int = 300


class PostgresSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="POSTGRES_", env_file=".env", extra="ignore")

    dsn: str = "postgresql+asyncpg://trade_pipeline:trade_pipeline@localhost:5432/trade_pipeline"


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    kafka: KafkaSettings = Field(default_factory=KafkaSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    postgres: PostgresSettings = Field(default_factory=PostgresSettings)


def load_config() -> AppConfig:
    return AppConfig()
