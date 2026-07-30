"""Pydantic request/response models for the API."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class EnrichmentFieldOut(BaseModel):
    data: dict | None
    error: str | None


class TradeOut(BaseModel):
    broker_id: str
    trade_id: str
    symbol: str
    qty: int
    price: Decimal
    timestamp: datetime
    # Read straight from the stored `trades.enrichment`/`enrichment_status`
    # columns (routes_trades.py never calls Temporal or enrichment services
    # on the request path) — None/"disabled" when the "enrichment_enabled"
    # feature flag is off, regardless of what's actually stored, so API
    # consumers see a stable response shape either way.
    enrichment: dict[str, EnrichmentFieldOut] | None = None
    enrichment_status: str = "not_requested"

    model_config = {"from_attributes": True}


class FeatureFlagOut(BaseModel):
    name: str
    enabled: bool


class FeatureFlagUpdate(BaseModel):
    enabled: bool
