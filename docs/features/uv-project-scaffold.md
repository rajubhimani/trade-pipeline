# Feature: uv project scaffold + local dev services

Status: shipped
Task: docs/tasks/completed/T-1-uv-project-scaffold.md, docs/tasks/completed/T-2-docker-compose.md

## Problem / motivation

The 8-week prep plan (`../../faang_python_full_prep.html`) requires a real, runnable project — not
just notes — and requires it to run and be compared across Python 3.11 through 3.14. That needs a
project layout and dependency manager that make multi-version work easy, plus a one-command local
environment for the services the pipeline depends on (Kafka, Redis, Postgres).

## Scope

In: `uv`-managed `trade-pipeline/` project with `src/` layout, `pyproject.toml` pinning
`requires-python = ">=3.11,<3.15"`, a dev dependency group (pytest, ruff, mypy, pip-audit), and
`docker-compose.yml` bringing up Zookeeper, Kafka, Redis, and Postgres.

Out: CI pipeline config, Kubernetes/deployment manifests — this is a local learning project, not a
deployment target (see `../ARCHITECTURE.md` non-goals).

## Design

- `uv init --lib` scaffolded the package; `pyproject.toml` was then hand-edited to add the real
  dependency set (confirmed against current stable versions via web research, not memory — see
  `../DECISIONS.md`).
- Dependencies pinned to lower bounds only (`>=`), resolved/locked by `uv sync` into `uv.lock` so the
  exact resolved graph is reproducible.
- `docker-compose.yml` originally used `confluentinc/cp-kafka`/`cp-zookeeper` 7.7.1, `redis:7.4-alpine`,
  `postgres:17-alpine`; upgraded to `apache/kafka:4.3.1` (KRaft, no Zookeeper), `redis:8.8-alpine`,
  `postgres:18.4-alpine` — current stable pinned versions, each verified against Docker Hub's registry
  API (not assumed) before adopting. See `../DECISIONS.md` "Kafka KRaft mode, not Zookeeper" and
  "Docker image versions verified against the registry, not guessed." Named volume for Postgres data
  only — Kafka/Redis are ephemeral by design for a dev environment that gets `docker-compose down -v`
  reset regularly (see Week 1-2 project track in the source HTML plan).

## Python version notes

`requires-python` spans 3.11–3.14 deliberately, per `../PYTHON_VERSION_NOTES.md` — the whole point of
the project is comparing behavior/APIs across that range, not just running on the newest interpreter.

## Testing plan

No app logic here to unit test; validated by `uv sync` succeeding and `uv run pytest` collecting/running
tests in the rest of the package (see other feature docs).
