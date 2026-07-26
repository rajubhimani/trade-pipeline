"""App configuration, loaded from a TOML file.

Uses stdlib ``tomllib`` (3.11+) — no third-party ``toml`` dependency, per
docs/PYTHON_VERSION_NOTES.md. ``tomllib`` is read-only by design (no dump),
which is fine here since config is authored by hand, not written by the app.
"""

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class KafkaConfig:
    bootstrap_servers: str
    topic: str


@dataclass(frozen=True, slots=True)
class RedisConfig:
    url: str
    dedup_ttl_seconds: int


@dataclass(frozen=True, slots=True)
class PostgresConfig:
    dsn: str


@dataclass(frozen=True, slots=True)
class AppConfig:
    kafka: KafkaConfig
    redis: RedisConfig
    postgres: PostgresConfig


def load_config(path: Path | None = None) -> AppConfig:
    """Load config from a TOML file, with env-var overrides for secrets.

    Env vars win over file values so the DSN/credentials never need to live in
    the repo (config.toml holds only non-secret defaults for local dev).
    """
    path = path or Path(__file__).parent.parent.parent.parent / "config.toml"
    with path.open("rb") as f:
        raw = tomllib.load(f)

    return AppConfig(
        kafka=KafkaConfig(
            bootstrap_servers=os.environ.get(
                "KAFKA_BOOTSTRAP_SERVERS", raw["kafka"]["bootstrap_servers"]
            ),
            topic=raw["kafka"]["topic"],
        ),
        redis=RedisConfig(
            url=os.environ.get("REDIS_URL", raw["redis"]["url"]),
            dedup_ttl_seconds=raw["redis"]["dedup_ttl_seconds"],
        ),
        postgres=PostgresConfig(
            dsn=os.environ.get("POSTGRES_DSN", raw["postgres"]["dsn"]),
        ),
    )
