"""
Forex API Router

REST API endpoints for forex data, charts, and alerts.
"""

from datetime import datetime
from typing import List, Optional, Literal
from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field

from app.forex.service import get_forex_service
from app.forex.models import AlertCondition, ForexPrice, PriceAlert, TechnicalIndicators
from app.core.logging import get_logger


logger = get_logger(__name__)
router = APIRouter(prefix="/forex", tags=["Forex"])


# ==================== Request/Response Models ====================

class PriceResponse(BaseModel):
    symbol: str
    bid: float
    ask: float
    mid: float
    spread: float
    spread_pips: float
    timestamp: datetime


class AllPricesResponse(BaseModel):
    prices: List[PriceResponse]
    count: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class CreateAlertRequest(BaseModel):
    guild_id: int
    user_id: int
    channel_id: int
    symbol: str
    condition: AlertCondition
    target_price: float


class AlertResponse(BaseModel):
    id: int
    guild_id: int
    user_id: int
    channel_id: int
    symbol: str
    condition: AlertCondition
    target_price: float
    created_at: datetime
    is_active: bool


class OHLCResponse(BaseModel):
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    is_bullish: bool


class ChartRequest(BaseModel):
    symbol: str
    timeframe: str = "1h"
    limit: int = 50
    show_ma: bool = True


# ==================== Endpoints ====================

@router.get("/price/{symbol}", response_model=PriceResponse)
async def get_price(symbol: str):
    """Get current price for a forex symbol"""
    service = get_forex_service()
    if not service:
        raise HTTPException(status_code=503, detail="Forex service not available")
    
    price = service.get_price(symbol)
    if not price:
        raise HTTPException(status_code=404, detail=f"No data for symbol: {symbol}")
    
    return PriceResponse(
        symbol=price.symbol.upper(),
        bid=price.bid,
        ask=price.ask,
        mid=price.mid,
        spread=price.spread,
        spread_pips=price.spread_pips,
        timestamp=price.timestamp,
    )


@router.get("/prices", response_model=AllPricesResponse)
async def get_all_prices():
    """Get all available forex prices"""
    service = get_forex_service()
    if not service:
        raise HTTPException(status_code=503, detail="Forex service not available")
    
    prices = service.get_all_prices()
    
    return AllPricesResponse(
        prices=[
            PriceResponse(
                symbol=p.symbol.upper(),
                bid=p.bid,
                ask=p.ask,
                mid=p.mid,
                spread=p.spread,
                spread_pips=p.spread_pips,
                timestamp=p.timestamp,
            )
            for p in prices.values()
        ],
        count=len(prices),
    )


@router.get("/ohlc/{symbol}", response_model=List[OHLCResponse])
async def get_ohlc(
    symbol: str,
    timeframe: str = Query("1h", regex="^(1m|5m|15m|1h|4h)$"),
    limit: int = Query(100, ge=1, le=500),
):
    """Get OHLC candlestick data"""
    service = get_forex_service()
    if not service:
        raise HTTPException(status_code=503, detail="Forex service not available")
    
    candles = service.get_ohlc(symbol, timeframe, limit)
    if not candles:
        raise HTTPException(status_code=404, detail=f"No OHLC data for symbol: {symbol}")
    
    return [
        OHLCResponse(
            symbol=c.symbol.upper(),
            timestamp=c.timestamp,
            open=c.open,
            high=c.high,
            low=c.low,
            close=c.close,
            is_bullish=c.is_bullish,
        )
        for c in candles
    ]


@router.get("/indicators/{symbol}", response_model=TechnicalIndicators)
async def get_indicators(
    symbol: str,
    timeframe: str = Query("1h", regex="^(1m|5m|15m|1h|4h)$"),
):
    """Get technical analysis indicators for a symbol"""
    service = get_forex_service()
    if not service:
        raise HTTPException(status_code=503, detail="Forex service not available")
    
    indicators = service.get_technical_indicators(symbol, timeframe)
    if not indicators:
        raise HTTPException(status_code=404, detail=f"Not enough data for symbol: {symbol}")
    
    return indicators


@router.get("/chart/{symbol}")
async def get_chart(
    symbol: str,
    timeframe: str = Query("1h", regex="^(1m|5m|15m|1h|4h)$"),
    limit: int = Query(50, ge=10, le=200),
    show_ma: bool = Query(True),
    chart_type: Literal["candlestick", "line"] = Query("candlestick"),
):
    """Generate and return a chart image (PNG)"""
    service = get_forex_service()
    if not service:
        raise HTTPException(status_code=503, detail="Forex service not available")
    
    if chart_type == "candlestick":
        image_bytes = service.generate_candlestick_chart(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
            show_ma=show_ma,
            output_format="bytes",
        )
    else:
        # Convert timeframe to minutes for line chart
        tf_minutes = {
            "1m": 1,
            "5m": 5,
            "15m": 15,
            "1h": 60,
            "4h": 240,
        }
        minutes = tf_minutes.get(timeframe, 60) * limit
        image_bytes = service.generate_line_chart(
            symbol=symbol,
            minutes=minutes,
            output_format="bytes",
        )
    
    if not image_bytes:
        raise HTTPException(status_code=404, detail=f"Cannot generate chart for symbol: {symbol}")
    
    return Response(
        content=image_bytes,
        media_type="image/png",
        headers={
            "Content-Disposition": f'inline; filename="{symbol}_{timeframe}.png"'
        }
    )


@router.get("/chart/compare")
async def get_comparison_chart(
    symbols: str = Query(..., description="Comma-separated symbols (e.g., eurusd,gbpusd,usdjpy)"),
    minutes: int = Query(60, ge=5, le=1440),
):
    """Generate a multi-pair comparison chart"""
    service = get_forex_service()
    if not service:
        raise HTTPException(status_code=503, detail="Forex service not available")
    
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    if len(symbol_list) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 symbols to compare")
    
    if len(symbol_list) > 6:
        raise HTTPException(status_code=400, detail="Maximum 6 symbols allowed")
    
    image_bytes = service.generate_comparison_chart(
        symbols=symbol_list,
        minutes=minutes,
        output_format="bytes",
    )
    
    if not image_bytes:
        raise HTTPException(status_code=404, detail="Cannot generate comparison chart")
    
    return Response(
        content=image_bytes,
        media_type="image/png",
    )


# ==================== Alerts ====================

@router.post("/alerts", response_model=AlertResponse)
async def create_alert(request: CreateAlertRequest):
    """Create a new price alert"""
    service = get_forex_service()
    if not service:
        raise HTTPException(status_code=503, detail="Forex service not available")
    
    # Verify symbol exists
    price = service.get_price(request.symbol)
    if not price:
        raise HTTPException(status_code=404, detail=f"Unknown symbol: {request.symbol}")
    
    alert = service.add_alert(
        guild_id=request.guild_id,
        user_id=request.user_id,
        channel_id=request.channel_id,
        symbol=request.symbol,
        condition=request.condition,
        target_price=request.target_price,
    )
    
    return AlertResponse(
        id=alert.id,
        guild_id=alert.guild_id,
        user_id=alert.user_id,
        channel_id=alert.channel_id,
        symbol=alert.symbol.upper(),
        condition=alert.condition,
        target_price=alert.target_price,
        created_at=alert.created_at,
        is_active=alert.is_active,
    )


@router.get("/alerts/user/{user_id}", response_model=List[AlertResponse])
async def get_user_alerts(user_id: int):
    """Get all alerts for a user"""
    service = get_forex_service()
    if not service:
        raise HTTPException(status_code=503, detail="Forex service not available")
    
    alerts = service.get_user_alerts(user_id)
    
    return [
        AlertResponse(
            id=a.id,
            guild_id=a.guild_id,
            user_id=a.user_id,
            channel_id=a.channel_id,
            symbol=a.symbol.upper(),
            condition=a.condition,
            target_price=a.target_price,
            created_at=a.created_at,
            is_active=a.is_active,
        )
        for a in alerts
    ]


@router.delete("/alerts/{alert_id}")
async def delete_alert(alert_id: int):
    """Delete an alert"""
    service = get_forex_service()
    if not service:
        raise HTTPException(status_code=503, detail="Forex service not available")
    
    removed = service.remove_alert(alert_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Alert not found: {alert_id}")
    
    return {"status": "deleted", "alert_id": alert_id}
