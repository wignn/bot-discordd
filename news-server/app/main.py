from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.api.v1.router import api_router


logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info(
        "Starting News Intelligence API",
        version="1.0.0",
        environment=settings.app_env,
    )
    
    # Start Forex Service
    if settings.forex_enabled and settings.tiingo_api_key:
        from app.forex.service import ForexService
        from app.forex.websocket import get_forex_ws_manager
        
        forex_service = ForexService.init_instance(settings.tiingo_api_key)
        await forex_service.start()
        
        # Register WebSocket manager
        ws_manager = get_forex_ws_manager()
        await ws_manager.register_with_service()
        
        logger.info("Forex Service started")
    
    yield
    
    # Stop Forex Service
    if settings.forex_enabled:
        from app.forex.service import get_forex_service
        service = get_forex_service()
        if service:
            await service.stop()
    
    logger.info("Shutting down News Intelligence API")


def create_app() -> FastAPI:
    
    app = FastAPI(
        title="News Intelligence API",
        description="Scalable News Intelligence Platform for Forex Trading",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
    )

    # CORS - allow frontend in production
    allowed_origins = ["*"] if settings.is_development else [
        "http://localhost:5173",
        "http://localhost:3000",
    ]
    # Add custom origins from environment if set
    if hasattr(settings, 'cors_origins') and settings.cors_origins:
        allowed_origins.extend(settings.cors_origins.split(','))
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api/v1")
    
    # Include Stock News router
    from app.stock.router import router as stock_router
    app.include_router(stock_router, prefix="/api/v1")

    @app.get("/health", tags=["Health"])
    async def health_check():
        return {
            "status": "healthy",
            "version": "1.0.0",
            "environment": settings.app_env,
        }

    @app.get("/", tags=["Root"])
    async def root():
        return {
            "name": "News Intelligence API",
            "version": "1.0.0",
            "docs": "/docs",
            "health": "/health",
        }

    # Forex WebSocket endpoint
    @app.websocket("/ws/forex")
    async def forex_websocket(websocket: WebSocket, client_id: str = "unknown", client_type: str = "unknown"):
        from app.forex.websocket import get_forex_ws_manager
        import uuid
        
        if client_id == "unknown":
            client_id = str(uuid.uuid4())[:8]
        
        manager = get_forex_ws_manager()
        await manager.connect(websocket, client_id, client_type)
        
        try:
            while True:
                data = await websocket.receive_json()
                await manager.handle_message(client_id, data)
        except WebSocketDisconnect:
            await manager.disconnect(client_id)
        except Exception as e:
            logger.error("Forex WebSocket error", error=str(e))
            await manager.disconnect(client_id)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.is_development,
        workers=1 if settings.is_development else settings.api_workers,
    )
