-- Indonesian Stock News Table
-- Separate from forex news to keep data organized

CREATE TABLE IF NOT EXISTS stock_news (
    id SERIAL PRIMARY KEY,
    content_hash VARCHAR(64) UNIQUE NOT NULL,
    original_url TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT,
    summary TEXT,
    
    source_name VARCHAR(255),
    category VARCHAR(50),  -- market, emiten, idx, corporate
    
    tickers TEXT,  -- Comma-separated: BBCA,TLKM,ASII
    
    sentiment VARCHAR(20),  -- bullish, bearish, neutral
    impact_level VARCHAR(20),  -- high, medium, low
    
    is_processed BOOLEAN DEFAULT FALSE,
    published_at TIMESTAMPTZ,
    processed_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_stock_news_processed_at ON stock_news(processed_at DESC);
CREATE INDEX IF NOT EXISTS idx_stock_news_tickers ON stock_news(tickers);
CREATE INDEX IF NOT EXISTS idx_stock_news_category ON stock_news(category);
CREATE INDEX IF NOT EXISTS idx_stock_news_sentiment ON stock_news(sentiment);
CREATE INDEX IF NOT EXISTS idx_stock_news_is_processed ON stock_news(is_processed);

-- Stock news channel subscriptions (separate from forex)
CREATE TABLE IF NOT EXISTS stock_news_channels (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    
    -- Filters
    tickers_filter TEXT,  -- Comma-separated tickers to filter, NULL = all
    min_impact VARCHAR(20) DEFAULT 'low',  -- Minimum impact level
    categories TEXT,  -- Comma-separated categories, NULL = all
    mention_everyone BOOLEAN DEFAULT FALSE,
    
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(guild_id, channel_id)
);

CREATE INDEX IF NOT EXISTS idx_stock_channels_guild ON stock_news_channels(guild_id);
CREATE INDEX IF NOT EXISTS idx_stock_channels_active ON stock_news_channels(is_active);
