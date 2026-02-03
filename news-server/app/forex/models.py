"""
Forex Data Models
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field, computed_field


class AlertCondition(str, Enum):
    ABOVE = "above"
    BELOW = "below"
    CROSS_UP = "cross_up"
    CROSS_DOWN = "cross_down"


class ForexPrice(BaseModel):
    """Real-time forex price data"""
    symbol: str
    bid: float
    ask: float
    mid: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    @computed_field
    @property
    def spread(self) -> float:
        return self.ask - self.bid
    
    @computed_field
    @property
    def spread_pips(self) -> float:
        symbol_upper = self.symbol.upper()
        if "JPY" in symbol_upper:
            multiplier = 100.0
        elif "XAU" in symbol_upper:
            multiplier = 10.0
        else:
            multiplier = 10000.0
        return self.spread * multiplier


class OHLC(BaseModel):
    """OHLC candlestick data"""
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = None
    
    @computed_field
    @property
    def is_bullish(self) -> bool:
        return self.close > self.open
    
    @computed_field
    @property
    def body_size(self) -> float:
        return abs(self.close - self.open)
    
    @computed_field
    @property
    def wick_upper(self) -> float:
        return self.high - max(self.open, self.close)
    
    @computed_field
    @property
    def wick_lower(self) -> float:
        return min(self.open, self.close) - self.low


class PriceAlert(BaseModel):
    """Price alert configuration"""
    id: int
    guild_id: int
    user_id: int
    channel_id: int
    symbol: str
    condition: AlertCondition
    target_price: float
    created_at: datetime = Field(default_factory=datetime.utcnow)
    triggered_at: Optional[datetime] = None
    is_active: bool = True


class TriggeredAlert(BaseModel):
    """Alert that has been triggered"""
    alert: PriceAlert
    triggered_price: float
    triggered_at: datetime = Field(default_factory=datetime.utcnow)


class PriceHistory(BaseModel):
    """Historical price data collection"""
    symbol: str
    timeframe: str  # "1m", "5m", "15m", "1h", "4h", "1d"
    candles: List[OHLC]
    
    @computed_field
    @property
    def latest_price(self) -> Optional[float]:
        if self.candles:
            return self.candles[-1].close
        return None


class TechnicalIndicators(BaseModel):
    """Technical analysis indicators"""
    symbol: str
    timestamp: datetime
    
    # Moving Averages
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None
    ema_12: Optional[float] = None
    ema_26: Optional[float] = None
    
    # Oscillators
    rsi_14: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    
    # Volatility
    atr_14: Optional[float] = None
    bollinger_upper: Optional[float] = None
    bollinger_middle: Optional[float] = None
    bollinger_lower: Optional[float] = None
    
    # Trend
    adx: Optional[float] = None
    
    @computed_field
    @property
    def trend_direction(self) -> str:
        if self.sma_20 and self.sma_50:
            if self.sma_20 > self.sma_50:
                return "bullish"
            elif self.sma_20 < self.sma_50:
                return "bearish"
        return "neutral"
    
    @computed_field
    @property
    def rsi_signal(self) -> str:
        if self.rsi_14:
            if self.rsi_14 >= 70:
                return "overbought"
            elif self.rsi_14 <= 30:
                return "oversold"
        return "neutral"
