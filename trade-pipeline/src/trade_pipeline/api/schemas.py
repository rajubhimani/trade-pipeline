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


class TradeOut(BaseModel):
    broker_id: str
    trade_id: str
    symbol: str
    qty: int
    price: Decimal
    timestamp: datetime

    model_config = {"from_attributes": True}
