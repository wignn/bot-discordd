from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.schemas import (
    NewsArticleResponse,
    NewsArticleListItem,
    NewsListResponse,
)


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
):
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
):
    return {"items": [], "count": 0}


@router.get("/high-impact")
async def get_high_impact_news(
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(20, ge=1, le=50),
):
    return {"items": [], "count": 0}


@router.get("/{article_id}", response_model=NewsArticleResponse)
async def get_news_article(article_id: UUID):
    raise HTTPException(status_code=404, detail="Article not found")


@router.get("/{article_id}/analysis")
async def get_article_analysis(article_id: UUID):
    raise HTTPException(status_code=404, detail="Article not found")


@router.post("/batch")
async def get_articles_batch(article_ids: list[UUID]):
    if len(article_ids) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 articles per request")
    
    return {"items": [], "count": 0}


@router.post("/{article_id}/reprocess")
async def reprocess_article(article_id: UUID):
    return {"message": "Article queued for reprocessing", "article_id": str(article_id)}
