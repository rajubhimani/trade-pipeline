from trade_pipeline.common.config import AppConfig, KafkaSettings, PostgresSettings, RedisSettings

_POSTGRES_ENV_VARS = (
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DB",
)
_REDIS_ENV_VARS = (
    "REDIS_HOST",
    "REDIS_PORT",
    "REDIS_DB",
    "REDIS_PASSWORD",
    "REDIS_DEDUP_TTL_SECONDS",
)


def test_defaults_match_local_docker_compose_setup(monkeypatch):
    for var in ("KAFKA_BOOTSTRAP_SERVERS", "KAFKA_TOPIC", *_REDIS_ENV_VARS, *_POSTGRES_ENV_VARS):
        monkeypatch.delenv(var, raising=False)

    config = AppConfig()

    assert config.kafka.bootstrap_servers == "localhost:9092"
    assert config.kafka.topic == "trades"
    assert config.redis.url == "redis://localhost:6379/0"
    assert config.redis.dedup_ttl_seconds == 300
    assert config.postgres.dsn == (
        "postgresql+asyncpg://trade_pipeline:trade_pipeline@localhost:5432/trade_pipeline"
    )
    assert config.postgres.sync_dsn == (
        "postgresql+psycopg://trade_pipeline:trade_pipeline@localhost:5432/trade_pipeline"
    )


def test_kafka_settings_env_var_overrides_default(monkeypatch):
    monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "broker.internal:9092")
    assert KafkaSettings().bootstrap_servers == "broker.internal:9092"


def test_redis_settings_env_var_overrides_default(monkeypatch):
    monkeypatch.setenv("REDIS_DEDUP_TTL_SECONDS", "600")
    assert RedisSettings().dedup_ttl_seconds == 600


def test_redis_settings_host_and_password_override_the_built_url(monkeypatch):
    monkeypatch.setenv("REDIS_HOST", "redis.internal")
    monkeypatch.setenv("REDIS_PASSWORD", "s3cret")

    assert RedisSettings().url == "redis://:s3cret@redis.internal:6379/0"


def test_redis_settings_url_has_no_auth_segment_when_password_unset(monkeypatch):
    monkeypatch.delenv("REDIS_PASSWORD", raising=False)
    assert RedisSettings().url == "redis://localhost:6379/0"


def test_postgres_settings_field_overrides_change_both_dsns(monkeypatch):
    monkeypatch.setenv("POSTGRES_HOST", "db.internal")
    monkeypatch.setenv("POSTGRES_USER", "svc")
    monkeypatch.setenv("POSTGRES_PASSWORD", "hunter2")
    monkeypatch.setenv("POSTGRES_DB", "custom")

    settings = PostgresSettings()

    assert settings.dsn == "postgresql+asyncpg://svc:hunter2@db.internal:5432/custom"
    assert settings.sync_dsn == "postgresql+psycopg://svc:hunter2@db.internal:5432/custom"


def test_env_var_wins_over_dotenv_file(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("KAFKA_TOPIC=from_dotenv\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("KAFKA_TOPIC", "from_real_env")

    assert KafkaSettings().topic == "from_real_env"


def test_dotenv_file_used_when_no_real_env_var_set(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("KAFKA_TOPIC=from_dotenv\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("KAFKA_TOPIC", raising=False)

    assert KafkaSettings().topic == "from_dotenv"
