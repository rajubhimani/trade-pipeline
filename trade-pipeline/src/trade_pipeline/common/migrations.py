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

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ALEMBIC_INI = _REPO_ROOT / "alembic.ini"


def upgrade_to_head(engine: Engine) -> None:
    config = Config(str(_ALEMBIC_INI))
    config.attributes["connection"] = engine
    upgrade(config, "head")
