# [done] pydantic-settings for configuration, with proper defaulting — id: T-20

Added: 2026-07-26
Completed: 2026-07-26
Notes: Not from the original plan — user asked whether dataclasses/Pydantic were used appropriately;
config loading was the real gap (hand-rolled dataclass + os.environ.get() + config.toml, not
pydantic-settings). Follow-up direction: .env locally, real env vars in production, proper defaulting.
Feature doc written first (docs/features/pydantic-settings.md).
Shipped: common/config.py rebuilt on pydantic_settings.BaseSettings (KafkaSettings/RedisSettings/
PostgresSettings, each with env_prefix + defaults matching docker-compose.yml exactly, composed into
AppConfig). api/settings.py split into ApiSettings (unchanged DI-friendly value object, kept exactly
as-is since tests construct it directly with in-memory keys) and new ApiEnvSettings (reads paths/CORS
from env/.env). Added trade-pipeline/.env.example documenting every setting; config.toml removed
entirely (superseded, not kept as a second redundant source).
Verified manually against real key files and a real .env override before trusting the design (not just
unit tests): confirmed .env precedence, confirmed load_api_settings() reads real generated RSA keys.
11 new tests (6 config, 5 api settings) covering defaults, env overrides, and .env-vs-real-env-var
precedence specifically. 100/100 tests passing project-wide, ruff clean, pip-audit clean.
Feature doc: docs/features/pydantic-settings.md
