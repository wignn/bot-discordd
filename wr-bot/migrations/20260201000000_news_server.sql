-- News Server tables migration
-- Tables for: news_sources, news_articles, news_analyses

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- News Sources table
CREATE TABLE IF NOT EXISTS news_sources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    
    source_type VARCHAR(50) NOT NULL,
    url TEXT NOT NULL,
    rss_url TEXT,
    
    scraper_config JSONB,
    
    language VARCHAR(10) DEFAULT 'en',
    country VARCHAR(50),
    category VARCHAR(100),
    
    reliability_score FLOAT DEFAULT 0.8,
    is_active BOOLEAN DEFAULT TRUE,
    
    fetch_interval INTEGER DEFAULT 300,
    last_fetched_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_sources_active ON news_sources(is_active);
CREATE INDEX IF NOT EXISTS idx_sources_type ON news_sources(source_type);
CREATE INDEX IF NOT EXISTS idx_sources_slug ON news_sources(slug);

-- News Articles table
CREATE TABLE IF NOT EXISTS news_articles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id UUID REFERENCES news_sources(id),
    
    content_hash VARCHAR(64) UNIQUE NOT NULL,
    
    original_url TEXT NOT NULL,
    original_title TEXT NOT NULL,
    original_content TEXT NOT NULL,
    original_language VARCHAR(10) DEFAULT 'en',
    
    translated_title TEXT,
    translated_content TEXT,
    
    summary TEXT,
    summary_bullets TEXT[],
    
    author VARCHAR(255),
    published_at TIMESTAMPTZ,
    image_url TEXT,
    tags TEXT[],
    
    is_processed BOOLEAN DEFAULT FALSE,
    processed_at TIMESTAMPTZ,
    processing_error TEXT,
    
    scraped_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_articles_published ON news_articles(published_at);
CREATE INDEX IF NOT EXISTS idx_articles_processed ON news_articles(is_processed);
CREATE INDEX IF NOT EXISTS idx_articles_source ON news_articles(source_id);
CREATE INDEX IF NOT EXISTS idx_articles_hash ON news_articles(content_hash);

-- News Analysis table
CREATE TABLE IF NOT EXISTS news_analyses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    article_id UUID UNIQUE REFERENCES news_articles(id),
    
    sentiment VARCHAR(20),
    sentiment_confidence FLOAT,
    sentiment_reasoning TEXT,
    
    impact_level VARCHAR(20),
    impact_score INTEGER,
    
    currencies TEXT[],
    currency_pairs TEXT[],
    organizations TEXT[],
    people TEXT[],
    events TEXT[],
    economic_indicators TEXT[],
    
    trading_recommendation JSONB,
    key_levels JSONB,
    
    ai_provider VARCHAR(50),
    ai_model VARCHAR(100),
    tokens_used INTEGER,
    processing_time_ms FLOAT,
    
    analyzed_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_analysis_sentiment ON news_analyses(sentiment);
CREATE INDEX IF NOT EXISTS idx_analysis_impact ON news_analyses(impact_level);
CREATE INDEX IF NOT EXISTS idx_analysis_currencies ON news_analyses USING GIN(currency_pairs);

-- Categories table
CREATE TABLE IF NOT EXISTS categories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) UNIQUE NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_categories_slug ON categories(slug);

-- API Keys table
CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    key_hash VARCHAR(64) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    
    is_active BOOLEAN DEFAULT TRUE,
    rate_limit INTEGER DEFAULT 100,
    
    request_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_apikeys_active ON api_keys(is_active);
CREATE INDEX IF NOT EXISTS idx_apikeys_hash ON api_keys(key_hash);

-- Insert default RSS sources
INSERT INTO news_sources (name, slug, source_type, url, rss_url, category, is_active)
VALUES 
    ('ForexFactory', 'forexfactory', 'rss', 'https://www.forexfactory.com', 'https://www.forexfactory.com/rss.php', 'forex', TRUE),
    ('Investing.com', 'investing', 'rss', 'https://www.investing.com', 'https://www.investing.com/rss/news.rss', 'forex', TRUE),
    ('FXStreet', 'fxstreet', 'rss', 'https://www.fxstreet.com', 'https://www.fxstreet.com/rss/news', 'forex', TRUE),
    ('DailyFX', 'dailyfx', 'rss', 'https://www.dailyfx.com', 'https://www.dailyfx.com/feeds/forex', 'forex', TRUE)
ON CONFLICT (slug) DO NOTHING;
