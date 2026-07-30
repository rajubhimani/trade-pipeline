"""Programmatic Alembic entrypoint.

Runs ``alembic upgrade head`` against an already-built engine, so callers
that already have one open (consumer/postgres_sink.init_schema,
scripts/migrate.py) don't open a second connection to Postgres just to
migrate — see migrations/env.py's ``run_migrations_online``.
"""

from pathlib import Path

from alembic.command import upgrade
from alembic.config import Config
from sqlalchemy import Engine


def _find_alembic_ini() -> Path:
    """A fixed ``parents[n]`` offset breaks depending on how this package
    got installed: in local/editable dev, this file lives under
    ``src/trade_pipeline/common/`` (3 parents to the repo root); in the
    Docker image, ``uv sync --no-editable`` installs it under
    ``.venv/lib/pythonX/site-packages/trade_pipeline/common/`` instead (4
    parents to ``/app``, where the Dockerfile separately copies
    ``alembic.ini``/``migrations/``) — a hardcoded offset silently pointed
    at the wrong directory there, producing an empty Alembic config with no
    error until ``upgrade()`` failed on a missing ``script_location``.
    Search upward instead of assuming either layout.
    """
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "alembic.ini"
        if candidate.exists():
            return candidate
    raise FileNotFoundError("alembic.ini not found in any parent directory of common/migrations.py")


def upgrade_to_head(engine: Engine) -> None:
    config = Config(str(_find_alembic_ini()))
    config.attributes["connection"] = engine
    upgrade(config, "head")
