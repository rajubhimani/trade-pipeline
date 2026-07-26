# Single image, multiple entrypoints — the producer, consumer, API, and
# Dagster all share the exact same dependency set (pyproject.toml/uv.lock),
# so one image selecting behavior via `command:` per docker-compose service
# is the correct pattern here, not four near-identical Dockerfiles.
#
# Multi-stage build following uv's own current documented pattern
# (docs.astral.sh/uv/guides/integration/docker/), verified before writing:
# builder stage resolves dependencies with cache mounts, final stage copies
# just the built venv + source into a plain slim Python image (no uv needed
# at runtime — smaller image, one less moving part in production).
#
# A separate Node stage builds the dashboard (dashboard/) into
# src/trade_pipeline/api/static/ before the Python builder stage copies the
# whole source tree — so the API's StaticFiles mount (api/main.py) has
# something to serve without requiring `npm run build` to have been run on
# the host first.

FROM node:24-slim AS dashboard-builder

# WORKDIR mirrors the real repo layout (trade-pipeline/dashboard/ next to
# trade-pipeline/src/) — vite.config.js's outDir ("../src/...") is relative
# to this directory, so it must resolve to /app/src/... to match where the
# Python builder stage below expects to find it.
WORKDIR /app/dashboard
COPY dashboard/package*.json ./
RUN npm ci
COPY dashboard/ ./
RUN npm run build

FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# Dependencies first, without the project itself, so this layer only
# rebuilds when pyproject.toml/uv.lock change, not on every source edit.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-editable

COPY . /app
# Overwrite whatever (nothing, if .dockerignore excludes it) was in
# src/trade_pipeline/api/static with the real build from the Node stage.
COPY --from=dashboard-builder /app/src/trade_pipeline/api/static /app/src/trade_pipeline/api/static

# --locked (not --frozen): fails the build if uv.lock is stale relative to
# pyproject.toml, rather than silently building from a mismatched lockfile —
# the correct flag for CI/production builds per current uv guidance.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-editable

FROM python:3.14-slim-bookworm

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src

# PATH activation, not `uv run`, at runtime — uv isn't needed once the venv
# is built, so it isn't in this final image at all (smaller, one fewer
# runtime dependency).
ENV PATH="/app/.venv/bin:$PATH"

# No default CMD — each docker-compose service (or `docker run`) picks its
# entrypoint explicitly, e.g.:
#   python -m trade_pipeline.producer.fake_trades
#   python -m trade_pipeline.consumer.dedup_consumer
#   uvicorn trade_pipeline.api.main:build_production_app --factory --host 0.0.0.0
#   dagster dev -m trade_pipeline.dagster_pipeline.definitions --host 0.0.0.0
