"""Stock News API Endpoints"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.logging import get_logger


logger = get_logger(__name__)
router = APIRouter()


@router.get("/latest")
async def get_latest_stock_news(
    limit: int = Query(default=10, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Get latest stock news from database"""
    try:
        result = await db.execute(
            text("""
                SELECT 
                    content_hash as id,
                    title,
                    summary,
                    source_name,
                    category,
                    tickers,
                    sentiment,
                    impact_level,
                    processed_at as published_at
                FROM stock_news
                WHERE is_processed = TRUE
                ORDER BY processed_at DESC
                LIMIT :limit
            """),
            {"limit": limit}
        )
        rows = result.fetchall()
        
        items = []
        for row in rows:
            items.append({
                "id": row.id,
                "content_hash": row.id,
                "title": row.title,
                "summary": row.summary,
                "source_name": row.source_name,
                "category": row.category,
                "tickers": row.tickers or "",
                "sentiment": row.sentiment,
                "impact_level": row.impact_level,
                "published_at": row.published_at.isoformat() if row.published_at else None,
                "processed_at": row.published_at.isoformat() if row.published_at else None,
            })
        
        return {
            "items": items,
            "total": len(items),
        }
    except Exception as e:
        logger.error("Failed to fetch stock news", error=str(e))
        return {"items": [], "total": 0, "error": str(e)}
