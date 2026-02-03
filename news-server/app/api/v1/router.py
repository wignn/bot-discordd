from fastapi import APIRouter

from app.api.v1.endpoints import news, sources, analytics, search, ai, websocket
from app.forex.router import router as forex_router


api_router = APIRouter()

api_router.include_router(news.router, prefix="/news", tags=["News"])
api_router.include_router(sources.router, prefix="/sources", tags=["Sources"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
api_router.include_router(search.router, prefix="/search", tags=["Search"])
api_router.include_router(ai.router, prefix="/ai", tags=["AI"])
api_router.include_router(websocket.router, prefix="/stream", tags=["WebSocket"])
api_router.include_router(forex_router, tags=["Forex"])

