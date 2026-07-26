from trade_pipeline.common.config import AppConfig, KafkaSettings, PostgresSettings, RedisSettings


def test_defaults_match_local_docker_compose_setup(monkeypatch):
    for var in ("KAFKA_BOOTSTRAP_SERVERS", "KAFKA_TOPIC", "REDIS_URL", "REDIS_DEDUP_TTL_SECONDS",
                "POSTGRES_DSN"):
        monkeypatch.delenv(var, raising=False)

    config = AppConfig()

    assert config.kafka.bootstrap_servers == "localhost:9092"
    assert config.kafka.topic == "trades"
    assert config.redis.url == "redis://localhost:6379/0"
    assert config.redis.dedup_ttl_seconds == 300
    assert "trade_pipeline" in config.postgres.dsn


def test_kafka_settings_env_var_overrides_default(monkeypatch):
    monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "broker.internal:9092")
    assert KafkaSettings().bootstrap_servers == "broker.internal:9092"


def test_redis_settings_env_var_overrides_default(monkeypatch):
    monkeypatch.setenv("REDIS_DEDUP_TTL_SECONDS", "600")
    assert RedisSettings().dedup_ttl_seconds == 600


def test_postgres_settings_env_var_overrides_default(monkeypatch):
    monkeypatch.setenv("POSTGRES_DSN", "postgresql+asyncpg://custom/db")
    assert PostgresSettings().dsn == "postgresql+asyncpg://custom/db"


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
