# Feature: Application Dockerfile

Status: shipped
Task: docs/tasks/completed/T-21-dockerfile.md

## Problem / motivation

`docker-compose.yml` only containerizes infrastructure (Kafka, Redis, Postgres) — the application
itself (producer, consumer, API, Dagster) runs via `uv run` on the host. User asked directly whether a
Dockerfile is needed. It is: it's the actual "how would you deploy this" answer for a system-design
conversation, and it's what would let `docker compose up` bring up the *entire* system, not just its
dependencies.

## Scope

In: a single multi-stage `Dockerfile` at `trade-pipeline/` root, producing one image used by every
component (producer, consumer, API, Dagster) — selecting behavior via the container's `command`
override per docker-compose service, not four separate Dockerfiles. This is the standard pattern for a
single-package monorepo-style project where every component shares one dependency set.

Out:
- Multi-image/per-component Dockerfiles — one shared image is simpler and correct here since every
  component uses the exact same `pyproject.toml`/`uv.lock` dependency set; splitting would only add
  build/maintenance overhead without a real benefit at this project's scale.
- A Kubernetes manifest / Helm chart — out of scope per `../ARCHITECTURE.md`'s existing non-goals
  ("No Kubernetes — Docker Compose only, this is a learning project, not a deployment target").
- Adding the app image to `docker-compose.yml` as a running service — the Dockerfile is built and
  documented as runnable, but docker-compose continues to run infra only; the app is still run via
  `uv run` locally for the fast edit-run loop development benefits from, per this project's existing
  patterns.

## Design

Verified the current `uv`-recommended pattern via research against Astral's own docs
(`docs.astral.sh/uv/guides/integration/docker/`) before writing anything, rather than working from
memory:

- **Base image**: `ghcr.io/astral-sh/uv:python3.14-bookworm-slim` for the builder stage (bundles uv +
  Python together — simpler than the alternative `COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx
  /bin/` trick onto a plain Python image, which is for when a specific unusual base image is needed).
  Pinned to the `python3.14-bookworm-slim` tag specifically, confirmed to exist and pull successfully
  before relying on it.
- **Multi-stage build**: dependencies resolved first without the project itself
  (`uv sync --locked --no-install-project --no-editable`), so that layer only rebuilds when
  `pyproject.toml`/`uv.lock` change, not on every source edit; the project is copied in and installed
  in a second `RUN` in the same builder stage. Final stage is a plain `python:3.14-slim-bookworm` image
  with just the built `.venv` and `src/` copied over — no `uv` in the final image at all.
- **`--locked`, not `--frozen`**: `--locked` fails the build outright if `uv.lock` is stale relative to
  `pyproject.toml`, which is the correct behavior for CI/production builds — `--frozen` (older
  guidance) just skips lock validation silently.
- **`UV_COMPILE_BYTECODE=1`, `UV_LINK_MODE=copy`, `UV_PYTHON_DOWNLOADS=0`** in the builder stage —
  `UV_LINK_MODE=copy` specifically matters because cache mounts (`--mount=type=cache`) don't support
  uv's default hardlink behavior across the cache/target boundary.
- **PATH activation at runtime (`ENV PATH="/app/.venv/bin:$PATH"`), not `uv run`** — avoids needing
  `uv` present in the final image at all, per current guidance for production images.
- **One image, no default `CMD`** — every entrypoint (producer, consumer, API, Dagster) is selected
  explicitly per `docker run`/docker-compose `command:` override, confirmed to be the standard
  recommended pattern for a single-package project with multiple entrypoints, not an anti-pattern.
- **Not added as a running docker-compose service** — the image is built and documented as runnable,
  but `docker-compose.yml` still brings up infra only; the app continues to run via `uv run` locally
  for the fast edit-run development loop this project already relies on.

## Python version notes

Base image pinned to a specific Python version (3.14, matching this project's primary dev interpreter)
— the Dockerfile is a single deployment target, not something that needs to run across the full
3.11–3.14 matrix the way local dev/CI does.

## Testing plan

No automated test (a Dockerfile isn't unit-testable in the usual sense) — verified manually, for real,
before considering this done:
- `docker build` succeeds.
- Producer entrypoint run inside the built image, on the docker-compose network, against the real
  Kafka broker — produced messages successfully.
- API entrypoint (`build_production_app()`) run inside the built image against real Postgres + Redis —
  built successfully, all 6 routes present (`/auth/*`, `/trades`, `/admin/feature-flags/*`, `/metrics`).
- Consumer entrypoint (`run_consumer`) run inside the built image against real Kafka + Redis +
  Postgres — processed 5 real messages end to end.
- Dagster `defs` importable inside the built image.
- All test containers/images cleaned up afterward (`docker rmi`, `docker compose down -v`) — nothing
  left running from verification.
