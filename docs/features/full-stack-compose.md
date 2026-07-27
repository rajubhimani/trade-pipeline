# Feature: Full-stack docker-compose (`make up`)

Status: shipped
Task: docs/tasks/completed/T-24-full-stack-compose.md

## Problem / motivation

User asked directly: "docker compose should have dockerfile setup in it right?" and "make up will up
everything". Until now `docker-compose.yml` only brought up infrastructure (Kafka, Redis, Postgres) —
the app's own producer/consumer/api/dagster processes had to be started by hand via `uv run` per
terminal, or via one-off `docker run` calls (see the superseded decision in `../DECISIONS.md`). That's
fine for active development but doesn't answer "bring the whole system up with one command."

## Scope

In:
- `producer`, `consumer`, `api`, `dagster` services in `docker-compose.yml`, all `build: .` (the
  existing `Dockerfile`), entrypoint selected via `command:`.
- `keys-init` one-shot service (`scripts/generate_keys.py`, new): generates the JWT RS256 keypair into
  a shared `keys` named volume — replaces the README's manual `openssl` steps, which have no host shell
  to target a container-only volume.
- `migrate` one-shot service (`scripts/migrate.py`, new): creates the schema + partitions before
  `api`/`consumer` start, so neither implicitly races the other into it.
- Real healthchecks on `kafka`/`redis`/`postgres` (`kafka-broker-api-versions.sh`, `redis-cli ping`,
  `pg_isready`) — app services gate on `condition: service_healthy` /
  `service_completed_successfully`, not compose's default "container started" ordering.
- `make up` / `make down` (`docker compose up -d --build` / `docker compose down -v`), plus `make ps`,
  `make logs`, `make restart`, and `make demo` (login as the demo user + fetch live trades — a
  one-command smoke check that producer→kafka→consumer→postgres→api are actually wired, not just
  "started").

Out:
- Automatic Kafka topic creation — the broker's own `auto.create.topics.enable` default handles it;
  adding a dedicated `kafka-init` service would duplicate behavior the broker already provides for
  free, for no benefit at this project's scale.
- Multi-replica / production orchestration concerns (readiness probes beyond healthchecks, resource
  limits, secrets management) — this is a local-dev/demo compose file, not a production deployment
  manifest.

## Design

See `../DECISIONS.md` ("`docker-compose.yml` runs the full stack, not just infrastructure (T-24)") for
the full writeup, including a real bug caught during verification: `ApiEnvSettings`'s default JWT key
paths were derived from `Path(__file__)`, which silently broke under the Dockerfile's
`uv sync --no-editable` install (package lives under `.venv/lib/.../site-packages/`, not `/app/src/`)
and crash-looped the `api` container. Fixed by defaulting to a plain relative path resolved against
the process's cwd instead.

`make` isn't installed on Windows by default — installed via `winget install ezwinports.make` (a real
GNU make, not a shim) so the same `Makefile` works identically across the team's dev machines rather
than needing a separate PowerShell-only wrapper.

## Testing plan

No new unit tests (this is infrastructure wiring, not application logic) — verified for real: `docker
compose down -v && docker compose up -d --build`, confirmed every service reaches a healthy/running
state, then exercised the actual data path end-to-end against the running stack: logged in via
`POST /auth/login`, queried `GET /trades` and got real rows the `producer`→`consumer` pipeline had
written, confirmed the dashboard serves at `/dashboard/`, `/metrics` on the consumer, and the Dagster
UI on `:3000`.
