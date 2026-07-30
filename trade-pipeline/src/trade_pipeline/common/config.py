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
    """Separate fields, not one pre-built URL — same reasoning as
    PostgresSettings: a managed Redis (ElastiCache, Azure Cache, etc.)
    almost always needs auth a local dev container doesn't, and a real
    deployment just overrides ``REDIS_HOST``/``REDIS_PASSWORD`` etc.
    individually rather than reconstructing a whole URL string.
    """

    model_config = SettingsConfigDict(env_prefix="REDIS_", env_file=".env", extra="ignore")

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    # None locally (docker-compose's redis service runs with no auth); a
    # real managed Redis sets this via REDIS_PASSWORD instead of baking
    # credentials into a URL.
    password: str | None = None
    dedup_ttl_seconds: int = 300

    @property
    def url(self) -> str:
        auth = f":{self.password}@" if self.password else ""
        return f"redis://{auth}{self.host}:{self.port}/{self.db}"


class PostgresSettings(BaseSettings):
    """Separate fields (user/password/host/port/db), not one pre-built DSN
    string — a single field meant changing the password required editing an
    embedded connection string in up to 5 places in docker-compose.yml; the
    host/port also differ between local (host-side) dev and containers
    (Compose DNS names), which separate fields make an ordinary env-var
    override instead of a different full string per environment.
    """

    model_config = SettingsConfigDict(env_prefix="POSTGRES_", env_file=".env", extra="ignore")

    user: str = "trade_pipeline"
    password: str = "trade_pipeline"
    host: str = "localhost"
    port: int = 5432
    db: str = "trade_pipeline"

    @property
    def dsn(self) -> str:
        """Async DSN (asyncpg) — used by the API and the Temporal worker."""
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"

    @property
    def sync_dsn(self) -> str:
        """Sync DSN (psycopg v3) — used by the consumer's sink and the
        one-shot migrate/dagster entrypoints. Was previously derived ad hoc
        via ``dsn.replace("+asyncpg", "+psycopg")`` at each of those 4 call
        sites; built from the same fields as ``dsn`` here instead.
        """
        return f"postgresql+psycopg://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"


class TemporalSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TEMPORAL_", env_file=".env", extra="ignore")

    address: str = "localhost:7233"
    # One task queue for both worked examples (EnrichmentWorkflow,
    # RefreshTokenRotationWorkflow) — a Temporal Worker binds to exactly one
    # task queue, and there's no reason to run two worker processes for two
    # low-volume demo workflows.
    task_queue: str = "trade-pipeline"
    # How often the outbox dispatcher (enrichment/outbox.py) polls
    # trade_enrichment_jobs for pending rows. Sub-second by default since a
    # missed dispatch just means a trade's enrichment shows up a bit later,
    # not lost data — the outbox row itself is already durably committed.
    outbox_poll_interval_seconds: float = 0.5


class EnrichmentSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ENRICHMENT_", env_file=".env", extra="ignore")

    # Absent by default — enrichment/services.py falls back to a
    # deterministic demo handler (varies by trade, not a fixed value) when a
    # given service has no configured URL. See docs/features/async-enrichment.md.
    risk_score_url: str | None = None
    sentiment_url: str | None = None


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    kafka: KafkaSettings = Field(default_factory=KafkaSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    postgres: PostgresSettings = Field(default_factory=PostgresSettings)
    temporal: TemporalSettings = Field(default_factory=TemporalSettings)
    enrichment: EnrichmentSettings = Field(default_factory=EnrichmentSettings)


def load_config() -> AppConfig:
    return AppConfig()
