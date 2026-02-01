import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
    Index,
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class NewsSource(Base):
    
    __tablename__ = "news_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    
    source_type = Column(String(50), nullable=False)
    url = Column(Text, nullable=False)
    rss_url = Column(Text, nullable=True)
    
    scraper_config = Column(JSONB, nullable=True)
    
    language = Column(String(10), default="en")
    country = Column(String(50), nullable=True)
    category = Column(String(100), nullable=True)
    
    reliability_score = Column(Float, default=0.8)
    is_active = Column(Boolean, default=True)
    
    fetch_interval = Column(Integer, default=300)
    last_fetched_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    articles = relationship("NewsArticle", back_populates="source")

    __table_args__ = (
        Index("idx_sources_active", "is_active"),
        Index("idx_sources_type", "source_type"),
    )


class NewsArticle(Base):
    
    __tablename__ = "news_articles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(UUID(as_uuid=True), ForeignKey("news_sources.id"), nullable=False)
    
    content_hash = Column(String(64), unique=True, nullable=False, index=True)
    
    original_url = Column(Text, nullable=False)
    original_title = Column(Text, nullable=False)
    original_content = Column(Text, nullable=False)
    original_language = Column(String(10), default="en")
    
    translated_title = Column(Text, nullable=True)
    translated_content = Column(Text, nullable=True)
    
    summary = Column(Text, nullable=True)
    summary_bullets = Column(ARRAY(Text), nullable=True)
    
    author = Column(String(255), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    image_url = Column(Text, nullable=True)
    tags = Column(ARRAY(String), nullable=True)
    
    is_processed = Column(Boolean, default=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    processing_error = Column(Text, nullable=True)
    
    scraped_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    source = relationship("NewsSource", back_populates="articles")
    analysis = relationship("NewsAnalysis", back_populates="article", uselist=False)

    __table_args__ = (
        Index("idx_articles_published", "published_at"),
        Index("idx_articles_processed", "is_processed"),
        Index("idx_articles_source", "source_id"),
    )


class NewsAnalysis(Base):
    
    __tablename__ = "news_analyses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    article_id = Column(UUID(as_uuid=True), ForeignKey("news_articles.id"), unique=True, nullable=False)
    
    sentiment = Column(String(20), nullable=True)
    sentiment_confidence = Column(Float, nullable=True)
    sentiment_reasoning = Column(Text, nullable=True)
    
    impact_level = Column(String(20), nullable=True)
    impact_score = Column(Integer, nullable=True)
    
    currencies = Column(ARRAY(String), nullable=True)
    currency_pairs = Column(ARRAY(String), nullable=True)
    organizations = Column(ARRAY(String), nullable=True)
    people = Column(ARRAY(String), nullable=True)
    events = Column(ARRAY(String), nullable=True)
    economic_indicators = Column(ARRAY(String), nullable=True)
    
    trading_recommendation = Column(JSONB, nullable=True)
    key_levels = Column(JSONB, nullable=True)
    
    ai_provider = Column(String(50), nullable=True)
    ai_model = Column(String(100), nullable=True)
    tokens_used = Column(Integer, nullable=True)
    processing_time_ms = Column(Float, nullable=True)
    
    analyzed_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    article = relationship("NewsArticle", back_populates="analysis")

    __table_args__ = (
        Index("idx_analysis_sentiment", "sentiment"),
        Index("idx_analysis_impact", "impact_level"),
        Index("idx_analysis_currencies", "currency_pairs", postgresql_using="gin"),
    )


class Category(Base):
    
    __tablename__ = "categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class APIKey(Base):
    
    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key_hash = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    
    is_active = Column(Boolean, default=True)
    rate_limit = Column(Integer, default=100)
    
    request_count = Column(Integer, default=0)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_apikeys_active", "is_active"),
    )
