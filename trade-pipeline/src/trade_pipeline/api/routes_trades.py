"""Read-only query endpoint over the trades table populated by the consumer.

Enrichment is read straight from the stored `trades.enrichment`/
`enrichment_status` columns — this endpoint never calls Temporal or an
enrichment service itself. Results get there durably out-of-band: the
consumer commits a trade + pending outbox job in one transaction
(consumer/postgres_sink.py), the Temporal worker's outbox dispatcher starts
one workflow per job (enrichment/outbox.py), and the workflow persists its
result back to the exact trade (enrichment/persistence.py). See
docs/features/async-enrichment.md.
"""

from fastapi import APIRouter, Query
from sqlalchemy import select

from trade_pipeline.api.dependencies import CurrentUserDep, SessionDep
from trade_pipeline.api.schemas import TradeOut
from trade_pipeline.common.db_models import Trade
from trade_pipeline.common.feature_flags import is_enabled

router = APIRouter(tags=["trades"])


@router.get("/trades", response_model=list[TradeOut])
async def list_trades(
    session: SessionDep,
    current_user: CurrentUserDep,
    symbol: str | None = Query(default=None),
    broker_id: str | None = Query(default=None),
    limit: int = Query(default=50, le=500, gt=0),
) -> list[TradeOut]:
    stmt = select(Trade).order_by(Trade.id.desc()).limit(limit)
    if symbol is not None:
        stmt = stmt.where(Trade.symbol == symbol)
    if broker_id is not None:
        stmt = stmt.where(Trade.broker_id == broker_id)

    result = await session.execute(stmt)
    rows = list(result.scalars().all())

    if await is_enabled(session, "enrichment_enabled"):
        return [TradeOut.model_validate(row) for row in rows]

    # "disabled" is an API-only presentation status, never written to the
    # DB (see common/db_models.Trade.enrichment_status) — stored results
    # stay in Postgres untouched and become visible again once the flag is
    # re-enabled.
    return [
        TradeOut.model_validate(row).model_copy(
            update={"enrichment": None, "enrichment_status": "disabled"}
        )
        for row in rows
    ]
