CREATE TABLE IF NOT EXISTS volatility_channels (
    id BIGSERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL UNIQUE,
    channel_id BIGINT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_volatility_channels_guild ON volatility_channels(guild_id);
CREATE INDEX IF NOT EXISTS idx_volatility_channels_active ON volatility_channels(is_active);
