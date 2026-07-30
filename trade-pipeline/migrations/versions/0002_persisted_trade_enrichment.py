"""persisted trade enrichment — trades.enrichment(_status) + trade_enrichment_jobs

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-30

Adds durable, per-trade Temporal enrichment (see
docs/features/async-enrichment.md and PROJECT_HANDOFF_TEMPORAL_ENRICHMENT.md):
a nullable JSONB column to hold the persisted enrichment result on the
exact trade row, an indexed status column driving both storage and the API's
"disabled" presentation state, and a transactional-outbox table
(``trade_enrichment_jobs``) so a trade insert and its pending enrichment job
always commit together.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("trades", sa.Column("enrichment", JSONB(), nullable=True))
    op.add_column(
        "trades",
        sa.Column(
            "enrichment_status",
            sa.String(length=32),
            nullable=False,
            server_default="not_requested",
        ),
    )
    op.create_index("ix_trades_enrichment_status", "trades", ["enrichment_status"])

    op.create_table(
        "trade_enrichment_jobs",
        sa.Column("workflow_id", sa.String(length=128), primary_key=True, nullable=False),
        sa.Column("broker_id", sa.String(length=64), nullable=False),
        sa.Column("trade_id", sa.String(length=64), nullable=False),
        sa.Column("trade_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_trade_enrichment_jobs_broker_id", "trade_enrichment_jobs", ["broker_id"])
    op.create_index("ix_trade_enrichment_jobs_trade_id", "trade_enrichment_jobs", ["trade_id"])
    op.create_index("ix_trade_enrichment_jobs_status", "trade_enrichment_jobs", ["status"])


def downgrade() -> None:
    op.drop_table("trade_enrichment_jobs")
    op.drop_index("ix_trades_enrichment_status", table_name="trades")
    op.drop_column("trades", "enrichment_status")
    op.drop_column("trades", "enrichment")
