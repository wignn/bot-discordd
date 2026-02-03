import asyncio
import json
from datetime import datetime
from enum import Enum
from typing import Any, Callable
from dataclasses import dataclass, field

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.core.logging import get_logger


logger = get_logger(__name__)


class EventType(str, Enum):
    NEWS_NEW = "news.new"
    NEWS_UPDATED = "news.updated"
    NEWS_HIGH_IMPACT = "news.high_impact"
    
    ANALYSIS_COMPLETE = "analysis.complete"
    SENTIMENT_ALERT = "sentiment.alert"
    
    SYSTEM_STATUS = "system.status"
    HEARTBEAT = "heartbeat"
    
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    SUBSCRIBED = "subscribed"
    ERROR = "error"


@dataclass
class WebSocketClient:
    websocket: WebSocket
    client_id: str
    connected_at: datetime = field(default_factory=datetime.utcnow)
    subscriptions: set[str] = field(default_factory=set)
    metadata: dict = field(default_factory=dict)
    client_type: str = "unknown"
    
    async def send(self, data: dict) -> bool:
        try:
            if self.websocket.client_state == WebSocketState.CONNECTED:
                await self.websocket.send_json(data)
                return True
        except Exception as e:
            logger.warning("Failed to send to client", client_id=self.client_id, error=str(e))
        return False


class WebSocketManager:

    def __init__(self):
        self.clients: dict[str, WebSocketClient] = {}
        self._lock = asyncio.Lock()
        self._event_handlers: dict[str, list[Callable]] = {}

    async def connect(
        self,
        websocket: WebSocket,
        client_id: str,
        client_type: str = "unknown",
        metadata: dict = None,
    ) -> WebSocketClient:
        await websocket.accept()
        
        client = WebSocketClient(
            websocket=websocket,
            client_id=client_id,
            client_type=client_type,
            metadata=metadata or {},
        )
        
        async with self._lock:
            if client_id in self.clients:
                await self.disconnect(client_id)
            
            self.clients[client_id] = client
        
        logger.info(
            "WebSocket client connected",
            client_id=client_id,
            client_type=client_type,
            total_clients=len(self.clients),
        )
        
        await client.send({
            "event": "connected",
            "client_id": client_id,
            "server_time": datetime.utcnow().isoformat(),
            "message": "Connected to News Intelligence WebSocket",
        })
        
        return client

    async def disconnect(self, client_id: str) -> None:
        async with self._lock:
            if client_id in self.clients:
                client = self.clients.pop(client_id)
                try:
                    await client.websocket.close()
                except Exception:
                    pass
                
                logger.info(
                    "WebSocket client disconnected",
                    client_id=client_id,
                    total_clients=len(self.clients),
                )

    async def subscribe(self, client_id: str, channels: list[str]) -> None:
        if client_id in self.clients:
            client = self.clients[client_id]
            client.subscriptions.update(channels)
            
            await client.send({
                "event": EventType.SUBSCRIBED,
                "channels": list(client.subscriptions),
            })
            
            logger.debug(
                "Client subscribed",
                client_id=client_id,
                channels=channels,
            )

    async def unsubscribe(self, client_id: str, channels: list[str]) -> None:
        if client_id in self.clients:
            client = self.clients[client_id]
            client.subscriptions.difference_update(channels)

    async def broadcast(
        self,
        event: EventType | str,
        data: dict,
        channel: str = None,
        client_type: str = None,
    ) -> int:
        message = {
            "event": event if isinstance(event, str) else event.value,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
            "channel": channel,
        }
        
        sent_count = 0
        disconnected = []
        
        for client_id, client in self.clients.items():
            if client_type and client.client_type != client_type:
                continue
            
            if channel and channel not in client.subscriptions:
                if "all" not in client.subscriptions:
                    continue
            
            success = await client.send(message)
            if success:
                sent_count += 1
            else:
                disconnected.append(client_id)
        
        for client_id in disconnected:
            await self.disconnect(client_id)
        
        if sent_count > 0:
            logger.debug(
                "Broadcast sent",
                event_type=str(event),
                sent_count=sent_count,
                channel=channel,
            )
        
        return sent_count

    async def send_to_client(self, client_id: str, event: str, data: dict) -> bool:
        if client_id in self.clients:
            return await self.clients[client_id].send({
                "event": event,
                "data": data,
                "timestamp": datetime.utcnow().isoformat(),
            })
        return False

    async def broadcast_to_discord_bots(self, event: EventType, data: dict) -> int:
        return await self.broadcast(event, data, client_type="discord_bot")

    async def handle_message(self, client_id: str, message: dict) -> None:
        event = message.get("event")
        data = message.get("data", {})
        
        if event == EventType.SUBSCRIBE:
            channels = data.get("channels", [])
            await self.subscribe(client_id, channels)
        
        elif event == EventType.UNSUBSCRIBE:
            channels = data.get("channels", [])
            await self.unsubscribe(client_id, channels)
        
        elif event == EventType.HEARTBEAT:
            await self.send_to_client(client_id, EventType.HEARTBEAT, {
                "server_time": datetime.utcnow().isoformat(),
            })
        
        else:
            handlers = self._event_handlers.get(event, [])
            for handler in handlers:
                try:
                    await handler(client_id, data)
                except Exception as e:
                    logger.error("Event handler error", event=event, error=str(e))

    def on_event(self, event: str):
        def decorator(func: Callable):
            if event not in self._event_handlers:
                self._event_handlers[event] = []
            self._event_handlers[event].append(func)
            return func
        return decorator

    @property
    def connection_count(self) -> int:
        return len(self.clients)

    @property
    def discord_bot_count(self) -> int:
        return sum(1 for c in self.clients.values() if c.client_type == "discord_bot")

    def get_stats(self) -> dict:
        client_types = {}
        for client in self.clients.values():
            client_types[client.client_type] = client_types.get(client.client_type, 0) + 1
        
        return {
            "total_connections": len(self.clients),
            "by_type": client_types,
            "discord_bots": self.discord_bot_count,
        }


ws_manager = WebSocketManager()


def get_ws_manager() -> WebSocketManager:
    return ws_manager
