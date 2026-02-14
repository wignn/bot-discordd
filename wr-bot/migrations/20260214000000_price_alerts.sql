CREATE TABLE IF NOT EXISTS price_alerts (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    guild_id BIGINT NOT NULL,
    symbol TEXT NOT NULL,
    target_price DOUBLE PRECISION NOT NULL,
    direction TEXT NOT NULL,
    is_triggered BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    triggered_at TIMESTAMPTZ
);

CREATE INDEX idx_price_alerts_active ON price_alerts(is_triggered, symbol);
CREATE INDEX idx_price_alerts_user ON price_alerts(user_id, is_triggered);
