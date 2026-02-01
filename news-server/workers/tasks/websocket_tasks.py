import asyncio
from datetime import datetime

from celery import shared_task

from app.core.logging import get_logger


logger = get_logger(__name__)


@shared_task(bind=True)
def send_heartbeat(self):
    async def _heartbeat():
        from app.websocket.manager import ws_manager, EventType
        
        stats = ws_manager.get_stats()
        
        if stats["total_connections"] > 0:
            await ws_manager.broadcast(
                event=EventType.HEARTBEAT,
                data={
                    "server_time": datetime.utcnow().isoformat(),
                    "connections": stats,
                },
                channel="system",
            )
            
            logger.debug(
                "Heartbeat sent",
                connections=stats["total_connections"],
            )
        
        return stats
    
    return asyncio.run(_heartbeat())


@shared_task(bind=True)
def broadcast_system_status(self):
    async def _status():
        from app.websocket.events import broadcast_system_status as ws_broadcast_status
        
        status = {
            "status": "healthy",
            "articles_24h": 0,
            "high_impact_24h": 0,
            "sources_active": 0,
            "processing_queue": 0,
        }
        
        count = await ws_broadcast_status(status)
        
        return {
            "status": status,
            "clients_notified": count,
        }
    
    return asyncio.run(_status())
