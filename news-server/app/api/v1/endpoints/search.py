from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query

from app.schemas import SearchQuery, SearchResponse


router = APIRouter()


@router.get("")
async def search_news(
    q: str = Query(..., min_length=2, description="Search query"),
    currency_pairs: Optional[list[str]] = Query(None),
    sentiment: Optional[str] = Query(None),
    impact_level: Optional[str] = Query(None),
    source_ids: Optional[list[str]] = Query(None),
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    return SearchResponse(
        items=[],
        total=0,
        page=page,
        page_size=page_size,
        total_pages=0,
        query=q,
        filters_applied={
            "currency_pairs": currency_pairs,
            "sentiment": sentiment,
            "impact_level": impact_level,
        },
    )


@router.post("")
async def search_news_post(query: SearchQuery):
    return SearchResponse(
        items=[],
        total=0,
        page=query.page,
        page_size=query.page_size,
        total_pages=0,
        query=query.q,
        filters_applied={},
    )


@router.get("/suggest")
async def search_suggestions(
    q: str = Query(..., min_length=2),
    limit: int = Query(5, ge=1, le=10),
):
    return {
        "suggestions": [],
        "query": q,
    }


@router.get("/similar/{article_id}")
async def find_similar_articles(
    article_id: str,
    limit: int = Query(5, ge=1, le=20),
):
    return {
        "article_id": article_id,
        "similar_articles": [],
    }
