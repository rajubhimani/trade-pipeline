"""Read-only query endpoint over the trades table populated by the consumer."""

from fastapi import APIRouter, Query
from sqlalchemy import select

from trade_pipeline.api.dependencies import CurrentUserDep, SessionDep
from trade_pipeline.api.schemas import TradeOut
from trade_pipeline.common.db_models import Trade

router = APIRouter(tags=["trades"])


@router.get("/trades", response_model=list[TradeOut])
async def list_trades(
    session: SessionDep,
    current_user: CurrentUserDep,
    symbol: str | None = Query(default=None),
    broker_id: str | None = Query(default=None),
    limit: int = Query(default=50, le=500, gt=0),
) -> list[Trade]:
    stmt = select(Trade).order_by(Trade.id.desc()).limit(limit)
    if symbol is not None:
        stmt = stmt.where(Trade.symbol == symbol)
    if broker_id is not None:
        stmt = stmt.where(Trade.broker_id == broker_id)

    result = await session.execute(stmt)
    return list(result.scalars().all())
