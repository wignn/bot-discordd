"""
Forex API Schemas for external clients (Discord bot, etc.)

These schemas define the WebSocket message protocol.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field


# ==================== WebSocket Message Types ====================

class WSMessageType(str, Enum):
    # Client -> Server
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    SUBSCRIBE_ALL = "subscribe_all"
    PING = "ping"
    GET_PRICE = "get_price"
    GET_CHART = "get_chart"
    CREATE_ALERT = "create_alert"
    DELETE_ALERT = "delete_alert"
    
    # Server -> Client
    SNAPSHOT = "snapshot"
    PRICE = "price"
    SUBSCRIBED = "subscribed"
    PONG = "pong"
    ALERT_TRIGGERED = "alert_triggered"
    CHART = "chart"
    ERROR = "error"


# ==================== Client Messages ====================

class SubscribeMessage(BaseModel):
    type: str = "subscribe"
    symbols: List[str]


class GetPriceMessage(BaseModel):
    type: str = "get_price"
    symbol: str


class GetChartMessage(BaseModel):
    type: str = "get_chart"
    symbol: str
    timeframe: str = "1h"
    limit: int = 50


class CreateAlertMessage(BaseModel):
    type: str = "create_alert"
    guild_id: int
    user_id: int
    channel_id: int
    symbol: str
    condition: str  # "above", "below", "cross_up", "cross_down"
    target_price: float


class DeleteAlertMessage(BaseModel):
    type: str = "delete_alert"
    alert_id: int


# ==================== Server Messages ====================

class PriceData(BaseModel):
    symbol: str
    bid: float
    ask: float
    mid: float
    spread_pips: float
    timestamp: str


class PriceMessage(BaseModel):
    type: str = "price"
    data: PriceData


class SnapshotMessage(BaseModel):
    type: str = "snapshot"
    data: Dict[str, PriceData]


class AlertTriggeredMessage(BaseModel):
    type: str = "alert_triggered"
    data: Dict[str, Any] = Field(default_factory=dict)
    """
    data contains:
    - alert_id: int
    - guild_id: int
    - user_id: int
    - channel_id: int
    - symbol: str
    - condition: str
    - target_price: float
    - triggered_price: float
    - triggered_at: str (ISO format)
    """


class ChartMessage(BaseModel):
    type: str = "chart"
    symbol: str
    timeframe: str
    image_base64: str


class ErrorMessage(BaseModel):
    type: str = "error"
    message: str
    code: Optional[str] = None
