from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

from app.core.logging import get_logger


logger = get_logger(__name__)
router = APIRouter(prefix="/stock", tags=["Stock News"])


class StockNewsResponse(BaseModel):
    id: str
    title: str
    summary: Optional[str]
    source_name: str
    original_url: str
    category: str
    tickers: list[str]
    sentiment: Optional[str]
    impact_level: Optional[str]
    published_at: Optional[str]
    processed_at: str


class StockNewsListResponse(BaseModel):
    items: list[StockNewsResponse]
    total: int
    page: int
    per_page: int


@router.get("/news", response_model=StockNewsListResponse)
async def get_stock_news(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    ticker: Optional[str] = Query(None, description="Filter by stock ticker (e.g., BBCA)"),
    category: Optional[str] = Query(None, description="Filter by category (market, emiten, idx)"),
    sentiment: Optional[str] = Query(None, description="Filter by sentiment (bullish, bearish, neutral)"),
):
    """Get Indonesian stock news with optional filters"""
    try:
        from sqlalchemy import text
        from app.db.session import get_sync_db
        
        # Build query
        query = """
            SELECT content_hash as id, title, summary, source_name, original_url,
                   category, tickers, sentiment, impact_level, 
                   published_at, processed_at
            FROM stock_news
            WHERE is_processed = TRUE
        """
        params = {}
        
        if ticker:
            query += " AND tickers ILIKE :ticker"
            params["ticker"] = f"%{ticker.upper()}%"
        
        if category:
            query += " AND category = :category"
            params["category"] = category
        
        if sentiment:
            query += " AND sentiment = :sentiment"
            params["sentiment"] = sentiment
        
        query += " ORDER BY processed_at DESC LIMIT :limit OFFSET :offset"
        params["limit"] = per_page
        params["offset"] = (page - 1) * per_page
        
        with get_sync_db() as session:
            result = session.execute(text(query), params)
            rows = result.fetchall()
            
            # Get total count
            count_query = "SELECT COUNT(*) FROM stock_news WHERE is_processed = TRUE"
            count_result = session.execute(text(count_query))
            total = count_result.scalar() or 0
        
        items = []
        for row in rows:
            tickers_str = row.tickers or ""
            items.append(StockNewsResponse(
                id=row.id,
                title=row.title,
                summary=row.summary,
                source_name=row.source_name,
                original_url=row.original_url,
                category=row.category or "market",
                tickers=tickers_str.split(",") if tickers_str else [],
                sentiment=row.sentiment,
                impact_level=row.impact_level,
                published_at=row.published_at.isoformat() if row.published_at else None,
                processed_at=row.processed_at.isoformat() if row.processed_at else datetime.now().isoformat(),
            ))
        
        return StockNewsListResponse(
            items=items,
            total=total,
            page=page,
            per_page=per_page,
        )
        
    except Exception as e:
        logger.error("Failed to get stock news", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tickers")
async def get_tracked_tickers():
    """Get list of frequently mentioned tickers"""
    try:
        from sqlalchemy import text
        from app.db.session import get_sync_db
        
        # This is a simple approach - in production you might want more sophisticated tracking
        with get_sync_db() as session:
            result = session.execute(text("""
                SELECT tickers, COUNT(*) as count
                FROM stock_news
                WHERE tickers IS NOT NULL AND tickers != ''
                GROUP BY tickers
                ORDER BY count DESC
                LIMIT 50
            """))
            rows = result.fetchall()
        
        # Parse and aggregate tickers
        ticker_counts = {}
        for row in rows:
            for ticker in row.tickers.split(","):
                ticker = ticker.strip().upper()
                if ticker and len(ticker) == 4:
                    ticker_counts[ticker] = ticker_counts.get(ticker, 0) + row.count
        
        # Sort by count
        sorted_tickers = sorted(ticker_counts.items(), key=lambda x: x[1], reverse=True)
        
        return {
            "tickers": [{"ticker": t, "mention_count": c} for t, c in sorted_tickers[:30]]
        }
        
    except Exception as e:
        logger.error("Failed to get tickers", error=str(e))
        return {"tickers": []}


@router.post("/collect")
async def trigger_collection():
    """Manually trigger stock news collection"""
    try:
        from workers.tasks.stock_tasks import fetch_stock_id_feeds
        
        fetch_stock_id_feeds.delay()
        
        return {"status": "scheduled", "message": "Stock news collection triggered"}
    except Exception as e:
        logger.error("Failed to trigger collection", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# WebSocket endpoint for stock news
from fastapi import WebSocket, WebSocketDisconnect
from app.stock.ws_manager import get_stock_ws_manager
import json


@router.websocket("/ws")
async def stock_websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time stock news"""
    manager = get_stock_ws_manager()
    connection = await manager.connect(websocket)
    
    logger.info("Stock WebSocket client connected")
    
    try:
        # Default subscription
        await manager.subscribe(connection, ["stock.new", "stock.high_impact"])
        
        # Send welcome message
        await manager.send_to_connection(connection, {
            "type": "connected",
            "message": "Connected to Stock News WebSocket",
            "channels": list(connection.subscribed_channels),
        })
        
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                action = message.get("action")
                
                if action == "subscribe":
                    channels = message.get("channels", [])
                    await manager.subscribe(connection, channels)
                    await manager.send_to_connection(connection, {
                        "type": "subscribed",
                        "channels": list(connection.subscribed_channels),
                    })
                
                elif action == "unsubscribe":
                    channels = message.get("channels", [])
                    await manager.unsubscribe(connection, channels)
                    await manager.send_to_connection(connection, {
                        "type": "unsubscribed",
                        "channels": list(connection.subscribed_channels),
                    })
                
                elif action == "ping":
                    await manager.send_to_connection(connection, {
                        "type": "pong",
                        "timestamp": datetime.now().isoformat(),
                    })
                    
            except json.JSONDecodeError:
                pass
                
    except WebSocketDisconnect:
        logger.info("Stock WebSocket client disconnected")
    finally:
        await manager.disconnect(connection)
