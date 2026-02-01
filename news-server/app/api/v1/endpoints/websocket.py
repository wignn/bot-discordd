import asyncio
import uuid
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException
from starlette.websockets import WebSocketState

from app.websocket.manager import ws_manager, EventType
from app.core.logging import get_logger


logger = get_logger(__name__)
router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    client_id: str = Query(default=None),
    client_type: str = Query(default="unknown"),
    token: str = Query(default=None),
):
    if not client_id:
        client_id = f"{client_type}-{uuid.uuid4().hex[:8]}"
    
    client = await ws_manager.connect(
        websocket=websocket,
        client_id=client_id,
        client_type=client_type,
        metadata={
            "connected_at": datetime.utcnow().isoformat(),
            "token": token,
        },
    )
    
    if client_type == "discord_bot":
        await ws_manager.subscribe(client_id, ["news", "high_impact", "sentiment", "all"])
    
    try:
        while True:
            try:
                data = await websocket.receive_json()
                await ws_manager.handle_message(client_id, data)
            except ValueError:
                await ws_manager.send_to_client(client_id, EventType.ERROR, {
                    "message": "Invalid JSON format",
                })
                
    except WebSocketDisconnect:
        logger.info("Client disconnected", client_id=client_id)
    except Exception as e:
        logger.error("WebSocket error", client_id=client_id, error=str(e))
    finally:
        await ws_manager.disconnect(client_id)


@router.websocket("/ws/discord")
async def discord_bot_endpoint(
    websocket: WebSocket,
    bot_id: str = Query(...),
    guild_id: str = Query(default=None),
    token: str = Query(default=None),
):
    client_id = f"discord-{bot_id}"
    
    client = await ws_manager.connect(
        websocket=websocket,
        client_id=client_id,
        client_type="discord_bot",
        metadata={
            "bot_id": bot_id,
            "guild_id": guild_id,
        },
    )
    
    await ws_manager.subscribe(client_id, [
        "all",
        "news",
        "high_impact",
        "sentiment",
        "system",
    ])
    
    try:
        while True:
            data = await websocket.receive_json()
            await ws_manager.handle_message(client_id, data)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("Discord WebSocket error", client_id=client_id, error=str(e))
    finally:
        await ws_manager.disconnect(client_id)


@router.get("/ws/stats")
async def get_ws_stats():
    return ws_manager.get_stats()


@router.get("/ws/clients")
async def list_ws_clients():
    clients = []
    for client_id, client in ws_manager.clients.items():
        clients.append({
            "client_id": client_id,
            "client_type": client.client_type,
            "connected_at": client.connected_at.isoformat(),
            "subscriptions": list(client.subscriptions),
            "metadata": client.metadata,
        })
    return {"clients": clients, "count": len(clients)}


@router.post("/ws/broadcast")
async def broadcast_message(
    event: str,
    data: dict,
    channel: str = None,
):
    count = await ws_manager.broadcast(
        event=event,
        data=data,
        channel=channel,
    )
    return {"sent_to": count, "event": event, "channel": channel}


@router.post("/ws/test-news")
async def test_news_broadcast():
    from app.websocket.events import broadcast_new_article
    
    test_article = {
        "id": "test-123",
        "original_title": "Federal Reserve Signals Potential Rate Cut in Q2",
        "translated_title": "Federal Reserve Memberikan Sinyal Pemotongan Suku Bunga di Q2",
        "summary": "The Fed indicated they may cut rates in the second quarter as inflation shows signs of cooling. Markets reacted positively with USD weakening against major pairs.",
        "source_name": "Test Source",
        "source_url": "https://example.com",
        "url": "https://example.com/article/123",
        "sentiment": "bearish",
        "sentiment_confidence": 0.78,
        "impact_level": "high",
        "impact_score": 8,
        "currency_pairs": ["EUR/USD", "GBP/USD", "USD/JPY"],
        "currencies": ["USD", "EUR", "GBP", "JPY"],
        "published_at": datetime.utcnow().isoformat(),
        "image_url": None,
    }
    
    count = await broadcast_new_article(test_article)
    
    return {
        "message": "Test news broadcasted",
        "clients_notified": count,
        "test_data": test_article,
    }


@router.post("/ws/test-high-impact")
async def test_high_impact_broadcast():
    from app.websocket.events import broadcast_high_impact_alert
    
    test_article = {
        "id": "test-alert-456",
        "original_title": "BREAKING: Fed Emergency Rate Cut of 50 Basis Points",
        "translated_title": "BREAKING: Fed Potong Suku Bunga Darurat 50 Basis Poin",
        "summary": "In an unexpected move, the Federal Reserve has announced an emergency rate cut.",
        "source_name": "Reuters",
        "url": "https://example.com/breaking",
        "sentiment": "bearish",
        "sentiment_confidence": 0.95,
        "impact_score": 10,
        "currency_pairs": ["EUR/USD", "USD/JPY", "GBP/USD", "USD/CHF"],
        "currencies": ["USD"],
        "published_at": datetime.utcnow().isoformat(),
    }
    
    count = await broadcast_high_impact_alert(test_article)
    
    return {
        "message": "High impact alert broadcasted",
        "clients_notified": count,
    }
