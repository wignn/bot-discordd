from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query


router = APIRouter()


@router.get("/sentiment")
async def get_sentiment_overview(
    hours: int = Query(24, ge=1, le=168),
    currency_pairs: Optional[list[str]] = Query(None),
):
    return {
        "overall_sentiment": "neutral",
        "confidence": 0.5,
        "period_hours": hours,
        "breakdown": {
            "bullish": 0,
            "bearish": 0,
            "neutral": 0,
        },
        "total_articles": 0,
    }


@router.get("/sentiment/{currency_pair}")
async def get_pair_sentiment(
    currency_pair: str,
    hours: int = Query(24, ge=1, le=168),
):
    return {
        "currency_pair": currency_pair,
        "sentiment": "neutral",
        "confidence": 0.5,
        "article_count": 0,
        "recent_news": [],
    }


@router.get("/trending")
async def get_trending_topics(
    hours: int = Query(24, ge=1, le=72),
    limit: int = Query(10, ge=1, le=50),
):
    return {
        "topics": [],
        "events": [],
        "currencies": [],
        "period_hours": hours,
    }


@router.get("/currencies/{currency}")
async def get_currency_analysis(
    currency: str,
    hours: int = Query(24, ge=1, le=168),
):
    return {
        "currency": currency.upper(),
        "news_count": 0,
        "sentiment": "neutral",
        "related_pairs": [],
        "key_events": [],
        "period_hours": hours,
    }


@router.get("/calendar")
async def get_economic_calendar(
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    impact: Optional[str] = Query(None, description="high, medium, low"),
    currencies: Optional[list[str]] = Query(None),
):
    return {
        "events": [],
        "total": 0,
    }


@router.get("/dashboard")
async def get_dashboard_data():
    return {
        "sentiment": {
            "overall": "neutral",
            "confidence": 0.5,
        },
        "high_impact_news": [],
        "trending_topics": [],
        "recent_articles": [],
        "stats": {
            "total_articles_24h": 0,
            "processed_articles_24h": 0,
            "active_sources": 0,
        },
    }
