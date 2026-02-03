"""
Tiingo WebSocket Client for Real-time Forex Data
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional, Callable, Dict, List, Any
from collections import deque

import websockets
from websockets.exceptions import ConnectionClosed

from app.core.logging import get_logger
from app.forex.models import ForexPrice, OHLC


logger = get_logger(__name__)

TIINGO_WS_URL = "wss://api.tiingo.com/fx"


class TiingoClient:
    """WebSocket client for Tiingo Forex API"""
    
    def __init__(
        self,
        api_key: str,
        on_price_update: Optional[Callable[[ForexPrice], None]] = None,
        threshold_level: int = 5,
    ):
        self.api_key = api_key
        self.on_price_update = on_price_update
        self.threshold_level = threshold_level
        
        self._prices: Dict[str, ForexPrice] = {}
        self._price_history: Dict[str, deque] = {}  # symbol -> deque of prices
        self._ohlc_data: Dict[str, Dict[str, List[OHLC]]] = {}  # symbol -> timeframe -> candles
        
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._running = False
        self._reconnect_delay = 5
        self._log_count = 0
        
        # For OHLC aggregation
        self._current_candles: Dict[str, Dict[str, dict]] = {}  # symbol -> timeframe -> candle_data
        
    @property
    def prices(self) -> Dict[str, ForexPrice]:
        return self._prices.copy()
    
    def get_price(self, symbol: str) -> Optional[ForexPrice]:
        return self._prices.get(symbol.lower())
    
    def get_all_prices(self) -> Dict[str, ForexPrice]:
        return self._prices.copy()
    
    def get_ohlc(self, symbol: str, timeframe: str = "1m", limit: int = 100) -> List[OHLC]:
        """Get OHLC candles for a symbol"""
        symbol_lower = symbol.lower()
        if symbol_lower in self._ohlc_data:
            if timeframe in self._ohlc_data[symbol_lower]:
                candles = self._ohlc_data[symbol_lower][timeframe]
                return candles[-limit:] if len(candles) > limit else candles
        return []
    
    def get_price_history(self, symbol: str, minutes: int = 60) -> List[ForexPrice]:
        """Get recent price history"""
        symbol_lower = symbol.lower()
        if symbol_lower in self._price_history:
            cutoff = datetime.utcnow() - timedelta(minutes=minutes)
            return [p for p in self._price_history[symbol_lower] if p.timestamp > cutoff]
        return []
    
    async def start(self):
        """Start the WebSocket connection with auto-reconnect"""
        self._running = True
        while self._running:
            try:
                await self._connect_and_run()
            except Exception as e:
                logger.error("Tiingo connection error", error=str(e))
            
            if self._running:
                logger.info(f"Reconnecting in {self._reconnect_delay} seconds...")
                await asyncio.sleep(self._reconnect_delay)
    
    async def stop(self):
        """Stop the WebSocket connection"""
        self._running = False
        if self._ws:
            await self._ws.close()
    
    async def _connect_and_run(self):
        """Connect to Tiingo and process messages"""
        logger.info("Connecting to Tiingo WebSocket...")
        
        async with websockets.connect(TIINGO_WS_URL) as ws:
            self._ws = ws
            logger.info("Connected to Tiingo WebSocket")
            
            # Send subscription message
            subscribe_msg = {
                "eventName": "subscribe",
                "authorization": self.api_key,
                "eventData": {
                    "thresholdLevel": self.threshold_level
                }
            }
            await ws.send(json.dumps(subscribe_msg))
            logger.info("Sent subscription message")
            
            # Process messages
            async for message in ws:
                await self._handle_message(message)
    
    async def _handle_message(self, message: str):
        """Process incoming WebSocket message"""
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            return
        
        message_type = data.get("messageType", "")
        
        if message_type == "A":
            # Price update
            await self._handle_price_update(data)
        elif message_type == "I":
            logger.info("Tiingo info", data=data)
        elif message_type == "E":
            logger.error("Tiingo error", data=data)
    
    async def _handle_price_update(self, data: dict):
        """Handle price update message"""
        msg_data = data.get("data", [])
        
        if not msg_data or len(msg_data) < 8:
            return
        
        update_type = msg_data[0]
        if update_type != "Q":  # Quote update
            return
        
        symbol = str(msg_data[1]).lower()
        bid = float(msg_data[4]) if msg_data[4] else 0.0
        ask = float(msg_data[7]) if msg_data[7] else 0.0
        
        if not symbol or bid <= 0 or ask <= 0:
            return
        
        # Validate spread (filter bad data)
        spread_pct = abs(ask - bid) / bid * 100
        if spread_pct > 1.0:
            return
        
        mid = (bid + ask) / 2.0
        
        price = ForexPrice(
            symbol=symbol,
            bid=bid,
            ask=ask,
            mid=mid,
            timestamp=datetime.utcnow()
        )
        
        # Store price
        self._prices[symbol] = price
        
        # Store in history (keep last 1000 per symbol)
        if symbol not in self._price_history:
            self._price_history[symbol] = deque(maxlen=1000)
        self._price_history[symbol].append(price)
        
        # Update OHLC candles
        self._update_ohlc(symbol, price)
        
        # Log first few prices
        self._log_count += 1
        if self._log_count <= 15:
            logger.info(f"[TIINGO] {symbol} bid={bid:.5f} ask={ask:.5f}")
        
        # Callback
        if self.on_price_update:
            try:
                if asyncio.iscoroutinefunction(self.on_price_update):
                    await self.on_price_update(price)
                else:
                    self.on_price_update(price)
            except Exception as e:
                logger.error("Price update callback error", error=str(e))
    
    def _update_ohlc(self, symbol: str, price: ForexPrice):
        """Aggregate prices into OHLC candles"""
        timeframes = {
            "1m": 60,
            "5m": 300,
            "15m": 900,
            "1h": 3600,
            "4h": 14400,
        }
        
        if symbol not in self._ohlc_data:
            self._ohlc_data[symbol] = {tf: [] for tf in timeframes}
        if symbol not in self._current_candles:
            self._current_candles[symbol] = {}
        
        for timeframe, seconds in timeframes.items():
            # Calculate candle start time
            ts = price.timestamp.timestamp()
            candle_start = datetime.utcfromtimestamp((ts // seconds) * seconds)
            
            if timeframe not in self._current_candles[symbol]:
                # Start new candle
                self._current_candles[symbol][timeframe] = {
                    "start": candle_start,
                    "open": price.mid,
                    "high": price.mid,
                    "low": price.mid,
                    "close": price.mid,
                }
            else:
                candle = self._current_candles[symbol][timeframe]
                
                if candle_start > candle["start"]:
                    # Close current candle and start new one
                    completed_candle = OHLC(
                        symbol=symbol,
                        timestamp=candle["start"],
                        open=candle["open"],
                        high=candle["high"],
                        low=candle["low"],
                        close=candle["close"],
                    )
                    
                    # Store completed candle (keep last 500 per timeframe)
                    self._ohlc_data[symbol][timeframe].append(completed_candle)
                    if len(self._ohlc_data[symbol][timeframe]) > 500:
                        self._ohlc_data[symbol][timeframe] = self._ohlc_data[symbol][timeframe][-500:]
                    
                    # Start new candle
                    self._current_candles[symbol][timeframe] = {
                        "start": candle_start,
                        "open": price.mid,
                        "high": price.mid,
                        "low": price.mid,
                        "close": price.mid,
                    }
                else:
                    # Update current candle
                    candle["high"] = max(candle["high"], price.mid)
                    candle["low"] = min(candle["low"], price.mid)
                    candle["close"] = price.mid
