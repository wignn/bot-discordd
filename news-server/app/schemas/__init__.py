from datetime import datetime
from typing import Optional, Literal
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
    total_pages: int


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: datetime


class NewsSourceBase(BaseModel):
    name: str
    url: str
    rss_url: Optional[str] = None
    source_type: Literal["rss", "scraper", "api"] = "rss"
    language: str = "en"
    category: Optional[str] = None
    is_active: bool = True


class NewsSourceCreate(NewsSourceBase):
    slug: str
    scraper_config: Optional[dict] = None


class NewsSourceResponse(NewsSourceBase):
    id: UUID
    slug: str
    reliability_score: float
    last_fetched_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class ContentBlock(BaseModel):
    original: str
    translated: Optional[str] = None


class AnalysisSentiment(BaseModel):
    value: Literal["bullish", "bearish", "neutral"]
    confidence: float = Field(ge=0, le=1)
    reasoning: Optional[str] = None


class AnalysisImpact(BaseModel):
    level: Literal["high", "medium", "low"]
    score: int = Field(ge=1, le=10)
    recommendation: Optional[dict] = None


class AnalysisEntities(BaseModel):
    currencies: list[str] = []
    currency_pairs: list[str] = []
    organizations: list[str] = []
    people: list[str] = []
    events: list[str] = []


class NewsAnalysisResponse(BaseModel):
    sentiment: AnalysisSentiment
    impact: AnalysisImpact
    entities: AnalysisEntities


class NewsArticleBase(BaseModel):
    original_url: str
    original_title: str
    published_at: Optional[datetime] = None


class NewsArticleResponse(BaseModel):
    id: UUID
    
    source: NewsSourceResponse
    
    title: ContentBlock
    content: ContentBlock
    summary: Optional[str] = None
    summary_bullets: list[str] = []
    
    analysis: Optional[NewsAnalysisResponse] = None
    
    original_url: str
    image_url: Optional[str] = None
    author: Optional[str] = None
    tags: list[str] = []
    
    published_at: Optional[datetime]
    scraped_at: datetime
    processed_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class NewsArticleListItem(BaseModel):
    id: UUID
    title: str
    title_id: Optional[str] = None
    summary: Optional[str] = None
    source_name: str
    sentiment: Optional[str] = None
    impact_level: Optional[str] = None
    currency_pairs: list[str] = []
    published_at: Optional[datetime]
    original_url: str


class NewsListResponse(PaginatedResponse):
    items: list[NewsArticleListItem]


class SentimentOverview(BaseModel):
    overall: Literal["bullish", "bearish", "neutral"]
    confidence: float
    bullish_count: int
    bearish_count: int
    neutral_count: int
    total_articles: int


class CurrencyAnalysis(BaseModel):
    pair: str
    sentiment: str
    article_count: int
    impact_average: float
    recent_news: list[NewsArticleListItem]


class TrendingTopic(BaseModel):
    topic: str
    mention_count: int
    sentiment: str
    related_pairs: list[str]


class SearchQuery(BaseModel):
    q: str = Field(min_length=2)
    currency_pairs: Optional[list[str]] = None
    sentiment: Optional[Literal["bullish", "bearish", "neutral"]] = None
    impact_level: Optional[Literal["high", "medium", "low"]] = None
    source_ids: Optional[list[UUID]] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    page: int = 1
    page_size: int = 20


class SearchResponse(PaginatedResponse):
    items: list[NewsArticleListItem]
    query: str
    filters_applied: dict
