from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import asyncio
import json

from fastapi import WebSocket


@dataclass
class StockWebSocketConnection:
    websocket: WebSocket
    subscribed_channels: set[str] = field(default_factory=set)
    connected_at: datetime = field(default_factory=datetime.utcnow)


class StockWebSocketManager:

    def __init__(self):
        self.connections: list[StockWebSocketConnection] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> StockWebSocketConnection:
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        conn = StockWebSocketConnection(websocket=websocket)
        async with self._lock:
            self.connections.append(conn)
        return conn

    async def disconnect(self, connection: StockWebSocketConnection):
        """Remove a WebSocket connection."""
        async with self._lock:
            if connection in self.connections:
                self.connections.remove(connection)

    async def subscribe(self, connection: StockWebSocketConnection, channels: list[str]):
        """Subscribe connection to specific channels."""
        connection.subscribed_channels.update(channels)

    async def unsubscribe(self, connection: StockWebSocketConnection, channels: list[str]):
        """Unsubscribe connection from specific channels."""
        connection.subscribed_channels.difference_update(channels)

    async def broadcast(self, channel: str, data: dict[str, Any]):
        """Broadcast message to all connections subscribed to the channel."""
        message = json.dumps({
            "event": channel,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        })

        async with self._lock:
            connections = list(self.connections)

        disconnected = []
        for conn in connections:
            # Send to connections subscribed to this channel or to "stock.*" wildcard
            if channel in conn.subscribed_channels or "stock.*" in conn.subscribed_channels:
                try:
                    await conn.websocket.send_text(message)
                except Exception:
                    disconnected.append(conn)

        # Clean up disconnected
        for conn in disconnected:
            await self.disconnect(conn)

    async def send_to_connection(self, connection: StockWebSocketConnection, data: dict[str, Any]):
        """Send message to a specific connection."""
        try:
            await connection.websocket.send_text(json.dumps(data))
        except Exception:
            await self.disconnect(connection)


# Global instance
stock_ws_manager = StockWebSocketManager()


def get_stock_ws_manager() -> StockWebSocketManager:
    """Get the global stock WebSocket manager instance."""
    return stock_ws_manager
