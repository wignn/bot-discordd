"""
Forex Service - Main Service Class

Coordinates price data, alerts, charts, and technical analysis.
"""

import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Callable, Any
from collections import defaultdict

from app.core.config import settings
from app.core.logging import get_logger
from app.forex.models import (
    ForexPrice, OHLC, PriceAlert, AlertCondition, 
    TriggeredAlert, TechnicalIndicators
)
from app.forex.tiingo_client import TiingoClient
from app.forex.charts import ChartGenerator
from app.forex.indicators import TechnicalAnalyzer


logger = get_logger(__name__)


class ForexService:
    """
    Main Forex Service
    
    Provides:
    - Real-time price data via Tiingo WebSocket
    - Price alerts with callbacks
    - Chart generation
    - Technical analysis
    """
    
    _instance: Optional["ForexService"] = None
    
    def __init__(self, tiingo_api_key: str):
        self._tiingo = TiingoClient(
            api_key=tiingo_api_key,
            on_price_update=self._on_price_update,
        )
        self._chart_generator = ChartGenerator()
        
        # Alerts storage
        self._alerts: Dict[int, PriceAlert] = {}  # id -> alert
        self._alert_id_counter = 1
        
        # Callbacks
        self._alert_callbacks: List[Callable[[TriggeredAlert], Any]] = []
        self._price_callbacks: List[Callable[[ForexPrice], Any]] = []
        
        # Previous prices for cross detection
        self._previous_prices: Dict[str, float] = {}
        
        self._running = False
    
    @classmethod
    def get_instance(cls) -> Optional["ForexService"]:
        """Get singleton instance"""
        return cls._instance
    
    @classmethod
    def init_instance(cls, tiingo_api_key: str) -> "ForexService":
        """Initialize singleton instance"""
        if cls._instance is None:
            cls._instance = cls(tiingo_api_key)
        return cls._instance
    
    # ==================== Price Data ====================
    
    def get_price(self, symbol: str) -> Optional[ForexPrice]:
        """Get current price for a symbol"""
        return self._tiingo.get_price(symbol)
    
    def get_all_prices(self) -> Dict[str, ForexPrice]:
        """Get all current prices"""
        return self._tiingo.get_all_prices()
    
    def get_ohlc(self, symbol: str, timeframe: str = "1m", limit: int = 100) -> List[OHLC]:
        """Get OHLC candles"""
        return self._tiingo.get_ohlc(symbol, timeframe, limit)
    
    def get_price_history(self, symbol: str, minutes: int = 60) -> List[ForexPrice]:
        """Get recent price history"""
        return self._tiingo.get_price_history(symbol, minutes)
    
    # ==================== Alerts ====================
    
    def add_alert(
        self,
        guild_id: int,
        user_id: int,
        channel_id: int,
        symbol: str,
        condition: AlertCondition,
        target_price: float,
    ) -> PriceAlert:
        """Add a new price alert"""
        alert = PriceAlert(
            id=self._alert_id_counter,
            guild_id=guild_id,
            user_id=user_id,
            channel_id=channel_id,
            symbol=symbol.lower(),
            condition=condition,
            target_price=target_price,
        )
        self._alerts[alert.id] = alert
        self._alert_id_counter += 1
        
        logger.info(
            "Alert created",
            alert_id=alert.id,
            symbol=symbol,
            condition=condition.value,
            target=target_price,
        )
        
        return alert
    
    def remove_alert(self, alert_id: int) -> bool:
        """Remove an alert by ID"""
        if alert_id in self._alerts:
            del self._alerts[alert_id]
            return True
        return False
    
    def get_user_alerts(self, user_id: int) -> List[PriceAlert]:
        """Get all alerts for a user"""
        return [a for a in self._alerts.values() if a.user_id == user_id and a.is_active]
    
    def get_all_alerts(self) -> List[PriceAlert]:
        """Get all active alerts"""
        return [a for a in self._alerts.values() if a.is_active]
    
    def on_alert_triggered(self, callback: Callable[[TriggeredAlert], Any]):
        """Register callback for triggered alerts"""
        self._alert_callbacks.append(callback)
    
    def on_price_update(self, callback: Callable[[ForexPrice], Any]):
        """Register callback for price updates"""
        self._price_callbacks.append(callback)
    
    # ==================== Charts ====================
    
    def generate_candlestick_chart(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 50,
        show_ma: bool = True,
        output_format: str = "bytes",
    ) -> Optional[bytes | str]:
        """Generate candlestick chart for a symbol"""
        candles = self.get_ohlc(symbol, timeframe, limit)
        if not candles:
            return None
        
        return self._chart_generator.generate_candlestick_chart(
            candles=candles,
            symbol=symbol,
            timeframe=timeframe,
            show_ma=show_ma,
            output_format=output_format,
        )
    
    def generate_line_chart(
        self,
        symbol: str,
        minutes: int = 60,
        output_format: str = "bytes",
    ) -> Optional[bytes | str]:
        """Generate line chart from recent prices"""
        prices = self.get_price_history(symbol, minutes)
        if not prices:
            return None
        
        return self._chart_generator.generate_line_chart(
            prices=prices,
            symbol=symbol,
            output_format=output_format,
        )
    
    def generate_comparison_chart(
        self,
        symbols: List[str],
        minutes: int = 60,
        output_format: str = "bytes",
    ) -> Optional[bytes | str]:
        """Generate multi-pair comparison chart"""
        data = {}
        for symbol in symbols:
            prices = self.get_price_history(symbol, minutes)
            if prices:
                data[symbol] = prices
        
        if not data:
            return None
        
        return self._chart_generator.generate_multi_pair_chart(
            data=data,
            output_format=output_format,
        )
    
    # ==================== Technical Analysis ====================
    
    def get_technical_indicators(self, symbol: str, timeframe: str = "1h") -> Optional[TechnicalIndicators]:
        """Calculate technical indicators for a symbol"""
        candles = self.get_ohlc(symbol, timeframe, 250)  # Need enough data for SMA 200
        if not candles or len(candles) < 20:
            return None
        
        return TechnicalAnalyzer.analyze(candles, symbol)
    
    # ==================== Lifecycle ====================
    
    async def start(self):
        """Start the forex service"""
        if self._running:
            return
        
        self._running = True
        logger.info("Starting Forex Service...")
        
        # Start Tiingo client in background
        asyncio.create_task(self._tiingo.start())
    
    async def stop(self):
        """Stop the forex service"""
        self._running = False
        await self._tiingo.stop()
        logger.info("Forex Service stopped")
    
    # ==================== Internal ====================
    
    async def _on_price_update(self, price: ForexPrice):
        """Handle price updates from Tiingo"""
        # Check alerts
        triggered = self._check_alerts(price)
        for alert in triggered:
            triggered_alert = TriggeredAlert(
                alert=alert,
                triggered_price=price.mid,
            )
            
            # Mark as triggered
            alert.is_active = False
            alert.triggered_at = datetime.utcnow()
            
            # Notify callbacks
            for callback in self._alert_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(triggered_alert)
                    else:
                        callback(triggered_alert)
                except Exception as e:
                    logger.error("Alert callback error", error=str(e))
        
        # Store previous price for cross detection
        self._previous_prices[price.symbol] = price.mid
        
        # Notify price callbacks
        for callback in self._price_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(price)
                else:
                    callback(price)
            except Exception as e:
                logger.error("Price callback error", error=str(e))
    
    def _check_alerts(self, price: ForexPrice) -> List[PriceAlert]:
        """Check if any alerts should be triggered"""
        triggered = []
        prev_price = self._previous_prices.get(price.symbol)
        
        for alert in self._alerts.values():
            if not alert.is_active:
                continue
            
            if alert.symbol.lower() != price.symbol.lower():
                continue
            
            should_trigger = False
            
            if alert.condition == AlertCondition.ABOVE:
                should_trigger = price.mid >= alert.target_price
            
            elif alert.condition == AlertCondition.BELOW:
                should_trigger = price.mid <= alert.target_price
            
            elif alert.condition == AlertCondition.CROSS_UP and prev_price:
                should_trigger = (
                    prev_price < alert.target_price <= price.mid
                )
            
            elif alert.condition == AlertCondition.CROSS_DOWN and prev_price:
                should_trigger = (
                    prev_price > alert.target_price >= price.mid
                )
            
            if should_trigger:
                triggered.append(alert)
        
        return triggered


# Global instance getter
def get_forex_service() -> Optional[ForexService]:
    """Get the global forex service instance"""
    return ForexService.get_instance()
