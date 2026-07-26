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
    # Only populated when the "enrichment_enabled" feature flag is on (see
    # common/feature_flags.py) — None otherwise, not omitted, so API
    # consumers see a stable response shape regardless of the flag state.
    enrichment: dict[str, EnrichmentFieldOut] | None = None

    model_config = {"from_attributes": True}


class FeatureFlagOut(BaseModel):
    name: str
    enabled: bool


class FeatureFlagUpdate(BaseModel):
    enabled: bool
