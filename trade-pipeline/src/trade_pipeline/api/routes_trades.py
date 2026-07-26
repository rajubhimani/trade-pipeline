"""Read-only query endpoint over the trades table populated by the consumer."""

from fastapi import APIRouter, Query, Request
from sqlalchemy import select

from trade_pipeline.api.dependencies import CurrentUserDep, SessionDep
from trade_pipeline.api.schemas import EnrichmentFieldOut, TradeOut
from trade_pipeline.common.db_models import Trade
from trade_pipeline.common.feature_flags import is_enabled
from trade_pipeline.enrichment.hand_rolled import enrich

router = APIRouter(tags=["trades"])


async def _enrichment_for_response(request: Request) -> dict[str, EnrichmentFieldOut]:
    """Run the hand-rolled enrichment fan-out (T-6) using the services/breakers
    kept on app.state so circuit-breaker state persists across requests, same
    as it would need to in a real long-running server (see api/main.py).
    """
    results = await enrich(
        request.app.state.enrichment_services,
        request.app.state.enrichment_breakers,
    )
    return {
        name: EnrichmentFieldOut(data=result.data, error=result.error)
        for name, result in results.items()
    }


@router.get("/trades", response_model=list[TradeOut])
async def list_trades(
    request: Request,
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
        enrichment = await _enrichment_for_response(request)
        return [
            TradeOut.model_validate(row).model_copy(update={"enrichment": enrichment})
            for row in rows
        ]

    return [TradeOut.model_validate(row) for row in rows]
