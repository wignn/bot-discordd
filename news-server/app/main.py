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
    
    yield
    
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

    allowed_origins = ["*"] if settings.is_development else [
        "http://localhost:5173",
        "http://localhost:3000",
        "https://forex.wign.cloud",
        "https://api.wign.cloud",
    ]
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
