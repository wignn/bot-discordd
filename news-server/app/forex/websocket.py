"""
Forex WebSocket Handler

Real-time price streaming via WebSocket for Discord bot and other clients.
"""

import asyncio
import json
from datetime import datetime
from typing import Set, Dict, Optional
from dataclasses import dataclass, field

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.forex.service import get_forex_service
from app.forex.models import ForexPrice, TriggeredAlert
from app.core.logging import get_logger


logger = get_logger(__name__)


@dataclass
class ForexClient:
    """WebSocket client for forex data"""
    websocket: WebSocket
    client_id: str
    connected_at: datetime = field(default_factory=datetime.utcnow)
    subscriptions: Set[str] = field(default_factory=set)  # subscribed symbols, empty = all
    client_type: str = "unknown"  # "bot", "web", etc.
    
    async def send(self, data: dict) -> bool:
        """Send data to client"""
        try:
            if self.websocket.client_state == WebSocketState.CONNECTED:
                await self.websocket.send_json(data)
                return True
        except Exception as e:
            logger.warning("Failed to send to forex client", client_id=self.client_id, error=str(e))
        return False


class ForexWebSocketManager:
    """Manages WebSocket connections for forex real-time data"""
    
    _instance: Optional["ForexWebSocketManager"] = None
    
    def __init__(self):
        self.clients: Dict[str, ForexClient] = {}
        self._lock = asyncio.Lock()
        self._registered = False
    
    @classmethod
    def get_instance(cls) -> "ForexWebSocketManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    async def register_with_service(self):
        """Register callbacks with forex service"""
        if self._registered:
            return
        
        service = get_forex_service()
        if service:
            service.on_price_update(self._broadcast_price)
            service.on_alert_triggered(self._broadcast_alert)
            self._registered = True
            logger.info("ForexWebSocketManager registered with ForexService")
    
    async def connect(self, websocket: WebSocket, client_id: str, client_type: str = "unknown"):
        """Handle new WebSocket connection"""
        await websocket.accept()
        
        client = ForexClient(
            websocket=websocket,
            client_id=client_id,
            client_type=client_type,
        )
        
        async with self._lock:
            self.clients[client_id] = client
        
        logger.info("Forex client connected", client_id=client_id, client_type=client_type)
        
        # Send current prices on connect
        service = get_forex_service()
        if service:
            prices = service.get_all_prices()
            await client.send({
                "type": "snapshot",
                "data": {
                    symbol: {
                        "symbol": p.symbol.upper(),
                        "bid": p.bid,
                        "ask": p.ask,
                        "mid": p.mid,
                        "spread_pips": p.spread_pips,
                        "timestamp": p.timestamp.isoformat(),
                    }
                    for symbol, p in prices.items()
                }
            })
    
    async def disconnect(self, client_id: str):
        """Handle client disconnect"""
        async with self._lock:
            if client_id in self.clients:
                del self.clients[client_id]
        
        logger.info("Forex client disconnected", client_id=client_id)
    
    async def handle_message(self, client_id: str, message: dict):
        """Handle incoming message from client"""
        msg_type = message.get("type", "")
        
        if msg_type == "subscribe":
            # Subscribe to specific symbols
            symbols = message.get("symbols", [])
            async with self._lock:
                if client_id in self.clients:
                    self.clients[client_id].subscriptions = set(s.lower() for s in symbols)
            
            await self._send_to_client(client_id, {
                "type": "subscribed",
                "symbols": symbols,
            })
        
        elif msg_type == "unsubscribe":
            # Unsubscribe from symbols
            symbols = message.get("symbols", [])
            async with self._lock:
                if client_id in self.clients:
                    self.clients[client_id].subscriptions -= set(s.lower() for s in symbols)
        
        elif msg_type == "subscribe_all":
            # Subscribe to all symbols
            async with self._lock:
                if client_id in self.clients:
                    self.clients[client_id].subscriptions = set()
            
            await self._send_to_client(client_id, {
                "type": "subscribed",
                "symbols": "all",
            })
        
        elif msg_type == "ping":
            await self._send_to_client(client_id, {"type": "pong"})
        
        elif msg_type == "get_price":
            symbol = message.get("symbol", "")
            service = get_forex_service()
            if service:
                price = service.get_price(symbol)
                if price:
                    await self._send_to_client(client_id, {
                        "type": "price",
                        "data": {
                            "symbol": price.symbol.upper(),
                            "bid": price.bid,
                            "ask": price.ask,
                            "mid": price.mid,
                            "spread_pips": price.spread_pips,
                            "timestamp": price.timestamp.isoformat(),
                        }
                    })
                else:
                    await self._send_to_client(client_id, {
                        "type": "error",
                        "message": f"Unknown symbol: {symbol}",
                    })
    
    async def _broadcast_price(self, price: ForexPrice):
        """Broadcast price update to subscribed clients"""
        message = {
            "type": "price",
            "data": {
                "symbol": price.symbol.upper(),
                "bid": price.bid,
                "ask": price.ask,
                "mid": price.mid,
                "spread_pips": price.spread_pips,
                "timestamp": price.timestamp.isoformat(),
            }
        }
        
        async with self._lock:
            for client in self.clients.values():
                # Check if client is subscribed to this symbol
                if not client.subscriptions or price.symbol.lower() in client.subscriptions:
                    asyncio.create_task(client.send(message))
    
    async def _broadcast_alert(self, triggered: TriggeredAlert):
        """Broadcast triggered alert to relevant client"""
        alert = triggered.alert
        
        message = {
            "type": "alert_triggered",
            "data": {
                "alert_id": alert.id,
                "guild_id": alert.guild_id,
                "user_id": alert.user_id,
                "channel_id": alert.channel_id,
                "symbol": alert.symbol.upper(),
                "condition": alert.condition.value,
                "target_price": alert.target_price,
                "triggered_price": triggered.triggered_price,
                "triggered_at": triggered.triggered_at.isoformat(),
            }
        }
        
        # Send to all connected bot clients
        async with self._lock:
            for client in self.clients.values():
                if client.client_type == "bot":
                    asyncio.create_task(client.send(message))
    
    async def _send_to_client(self, client_id: str, data: dict):
        """Send message to specific client"""
        async with self._lock:
            if client_id in self.clients:
                await self.clients[client_id].send(data)


# Global instance
def get_forex_ws_manager() -> ForexWebSocketManager:
    return ForexWebSocketManager.get_instance()
