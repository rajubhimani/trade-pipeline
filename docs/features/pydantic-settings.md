# Feature: pydantic-settings for configuration, with proper defaulting

Status: shipped
Task: docs/tasks/completed/T-20-pydantic-settings.md

## Problem / motivation

User asked directly whether dataclasses/Pydantic models were being used appropriately across the
project. Answer: Pydantic `BaseModel` was already correct for API-boundary schemas
(`api/schemas.py`) and dataclasses correct for internal value objects (`TradeEvent`, `ArchiveResult`,
etc.) — but configuration loading (`common/config.py`, `api/settings.py`) was hand-rolled dataclasses +
manual `os.environ.get()` calls layered over a `config.toml` file, not `pydantic-settings`, which is
the current idiomatic choice for this exact problem (typed validation, clear errors on missing/invalid
values, `.env` file support built in). Follow-up direction: local development uses a `.env` file,
production uses real environment variables set by the deployment environment, and every setting needs
a proper, sensible default.

## Scope

In:
- `common/config.py` rebuilt on `pydantic_settings.BaseSettings`: `KafkaSettings`, `RedisSettings`,
  `PostgresSettings` (each with an `env_prefix` and a baked-in default matching this project's local
  dev docker-compose setup), composed into `AppConfig`. `load_config()` becomes a one-line
  `AppConfig()` call — validation, defaulting, and `.env`/env-var precedence are what `BaseSettings`
  does natively.
- `api/settings.py` split into two: `ApiSettings` (unchanged shape — a plain dataclass holding actual
  key *content* and parsed CORS origins, kept exactly as-is because tests construct it directly with
  in-memory-generated RSA keys, not file paths) and a new `ApiEnvSettings(BaseSettings)` reading key
  *file paths* and raw CORS string from `.env`/env vars with defaults. `load_api_settings()` builds
  `ApiEnvSettings()`, reads the key files, and constructs the `ApiSettings` value object from that.
- `trade-pipeline/.env.example` — every available setting documented with its default value, committed
  to the repo; `.env` itself (real local overrides) is gitignored.
- `config.toml` removed — superseded by `BaseSettings` defaults + `.env`.

Out:
- Secrets manager integration (AWS Secrets Manager, Vault, etc.) — out of scope for a local/demo
  project; `.env`/real env vars are the two tiers this project actually needs.

## Design

- **Why split `ApiSettings` from `ApiEnvSettings`, not one class**: `ApiSettings` needs to stay a
  plain, trivially-constructible value object because `tests/api/conftest.py` builds one directly with
  an in-memory-generated ephemeral RSA keypair (PEM content, not a file path) — this is exactly the
  dependency-injection pattern already used throughout this codebase (`create_app` vs
  `build_production_app`, `DbEngineResource` vs a hardcoded engine). `ApiEnvSettings` is the
  environment-reading half, used only by the real `load_api_settings()` production path.
- **Defaults match the existing local dev docker-compose setup exactly** — `localhost:9092` for Kafka,
  `redis://localhost:6379/0`, the `trade_pipeline`/`trade_pipeline` Postgres credentials already in
  `docker-compose.yml` — so `AppConfig()` with zero configuration "just works" against
  `docker compose up -d`, matching this project's existing "it should just work locally" bar.
- **`.env` for local, real env vars for production, in that precedence order** — `pydantic-settings`'s
  own defined precedence (init args > env vars > `.env` file > defaults) already does the right thing:
  a real deployment's env vars always win over a stray `.env` file that happens to be present.

> **Update**: `PostgresSettings`/`RedisSettings` were later split into individual fields
> (`POSTGRES_HOST`/`PORT`/`USER`/`PASSWORD`/`DB`, `REDIS_HOST`/`PORT`/`DB`/`PASSWORD`) instead of one
> prebuilt DSN/URL each, computed via `.dsn`/`.sync_dsn`/`.url` properties — so pointing at a real
> managed Postgres/Redis later is overriding a couple of env vars, not reconstructing a whole
> connection string. `.env.example` is now one template reused for every `*.env` target (`.env` for
> host-side dev with `localhost` defaults, `docker-compose.env` for the full containerized stack with
> Compose service DNS names swapped in) rather than assuming `AppConfig()`'s bare defaults work
> against every `docker compose up` variant.

## Python version notes

No version-gated syntax; targets the full 3.11–3.14 range.

## Testing plan

- No test changes required for `ApiSettings` itself (unchanged shape, existing tests keep constructing
  it directly) — confirmed via the full existing API test suite passing unchanged.
- 6 new tests (`tests/common/test_config.py`): defaults match the local docker-compose setup exactly,
  per-setting env var overrides, `.env` file picked up when no real env var is set, and — the case that
  actually matters — a real env var wins over a conflicting `.env` file value.
- 5 new tests (`tests/api/test_settings.py`): `ApiEnvSettings` defaults, CORS comma-separated parsing,
  env var overriding a key path, `load_api_settings()` reading real (tmp-path) key files end to end,
  `DEFAULT_KEYS_DIR` sanity check.
- Verified manually against real key files and a real `.env` override before writing the automated
  tests, not just trusted the design: generated a real RSA keypair, confirmed `load_api_settings()`
  reads it correctly; wrote a real `.env` with `KAFKA_TOPIC=overridden_topic` and confirmed
  `load_config()` picks it up.
- 100/100 tests passing project-wide, ruff clean, pip-audit clean.
