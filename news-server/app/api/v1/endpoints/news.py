from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import NewsArticle, NewsAnalysis, NewsSource
from app.schemas import (
    NewsArticleResponse,
    NewsArticleListItem,
    NewsListResponse,
)
from app.core.logging import get_logger


logger = get_logger(__name__)
router = APIRouter()


@router.get("", response_model=NewsListResponse)
async def list_news(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    source_id: Optional[UUID] = None,
    sentiment: Optional[str] = None,
    impact_level: Optional[str] = None,
    currency_pair: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db),
):
    try:
        query = select(NewsArticle).order_by(desc(NewsArticle.created_at))
        
        if source_id:
            query = query.where(NewsArticle.source_id == source_id)
        if date_from:
            query = query.where(NewsArticle.published_at >= date_from)
        if date_to:
            query = query.where(NewsArticle.published_at <= date_to)
        
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        
        result = await db.execute(query)
        articles = result.scalars().all()
        
        items = []
        for article in articles:
            items.append(NewsArticleListItem(
                id=article.id,
                source_id=article.source_id,
                original_title=article.original_title,
                translated_title=article.translated_title,
                summary=article.summary,
                published_at=article.published_at,
                sentiment=None,
                impact_level=None,
                currency_pairs=[],
            ))
        
        return NewsListResponse(
            items=items,
            total=len(items),
            page=page,
            page_size=page_size,
            total_pages=max(1, (len(items) + page_size - 1) // page_size),
        )
    except Exception as e:
        logger.error("Error listing news", error=str(e))
        return NewsListResponse(
            items=[],
            total=0,
            page=page,
            page_size=page_size,
            total_pages=0,
        )


@router.get("/latest")
async def get_latest_news(
    limit: int = Query(10, ge=1, le=50),
    currency_pairs: Optional[list[str]] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    try:
        # Query articles with optional join to analysis
        query = (
            select(NewsArticle)
            .order_by(desc(NewsArticle.created_at))
            .limit(limit)
        )
        
        result = await db.execute(query)
        articles = result.scalars().all()
        
        items = []
        for article in articles:
            # Try to get analysis data if available
            analysis_query = select(NewsAnalysis).where(NewsAnalysis.article_id == article.id)
            analysis_result = await db.execute(analysis_query)
            analysis = analysis_result.scalar_one_or_none()
            
            # Get source name
            source_name = "Unknown"
            if article.source_id:
                source_query = select(NewsSource).where(NewsSource.id == article.source_id)
                source_result = await db.execute(source_query)
                source = source_result.scalar_one_or_none()
                if source:
                    source_name = source.name
            
            items.append({
                "id": str(article.id),
                "original_title": article.original_title,
                "translated_title": article.translated_title,
                "summary": article.summary,
                "source_name": source_name,
                "original_url": article.original_url,
                "image_url": article.image_url,
                "published_at": article.published_at.isoformat() if article.published_at else None,
                "created_at": article.created_at.isoformat() if article.created_at else None,
                "sentiment": analysis.sentiment if analysis else "neutral",
                "sentiment_confidence": analysis.sentiment_confidence if analysis else None,
                "impact_level": analysis.impact_level if analysis else "medium",
                "impact_score": analysis.impact_score if analysis else None,
                "currency_pairs": analysis.currency_pairs if analysis else [],
                "currencies": analysis.currencies if analysis else [],
            })
        
        return {"items": items, "count": len(items)}
        
    except Exception as e:
        logger.error("Error fetching latest news", error=str(e))
        return {"items": [], "count": 0, "error": str(e)}


@router.get("/high-impact")
async def get_high_impact_news(
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    try:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        # Query articles with high impact analysis
        query = (
            select(NewsArticle)
            .join(NewsAnalysis, NewsAnalysis.article_id == NewsArticle.id)
            .where(NewsArticle.created_at >= cutoff)
            .where(NewsAnalysis.impact_level == "high")
            .order_by(desc(NewsArticle.created_at))
            .limit(limit)
        )
        
        result = await db.execute(query)
        articles = result.scalars().all()
        
        items = []
        for article in articles:
            analysis_query = select(NewsAnalysis).where(NewsAnalysis.article_id == article.id)
            analysis_result = await db.execute(analysis_query)
            analysis = analysis_result.scalar_one_or_none()
            
            items.append({
                "id": str(article.id),
                "original_title": article.original_title,
                "translated_title": article.translated_title,
                "summary": article.summary,
                "published_at": article.published_at.isoformat() if article.published_at else None,
                "sentiment": analysis.sentiment if analysis else None,
                "impact_level": analysis.impact_level if analysis else None,
                "impact_score": analysis.impact_score if analysis else None,
                "currency_pairs": analysis.currency_pairs if analysis else [],
            })
        
        return {"items": items, "count": len(items)}
        
    except Exception as e:
        logger.error("Error fetching high impact news", error=str(e))
        return {"items": [], "count": 0}


@router.get("/{article_id}", response_model=NewsArticleResponse)
async def get_news_article(article_id: UUID, db: AsyncSession = Depends(get_db)):
    query = select(NewsArticle).where(NewsArticle.id == article_id)
    result = await db.execute(query)
    article = result.scalar_one_or_none()
    
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    return article


@router.get("/{article_id}/analysis")
async def get_article_analysis(article_id: UUID, db: AsyncSession = Depends(get_db)):
    query = select(NewsAnalysis).where(NewsAnalysis.article_id == article_id)
    result = await db.execute(query)
    analysis = result.scalar_one_or_none()
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Article not found")
    
    return analysis


@router.post("/batch")
async def get_articles_batch(article_ids: list[UUID], db: AsyncSession = Depends(get_db)):
    if len(article_ids) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 articles per request")
    
    query = select(NewsArticle).where(NewsArticle.id.in_(article_ids))
    result = await db.execute(query)
    articles = result.scalars().all()
    
    return {"items": articles, "count": len(articles)}


@router.post("/{article_id}/reprocess")
async def reprocess_article(article_id: UUID):
    return {"message": "Article queued for reprocessing", "article_id": str(article_id)}
