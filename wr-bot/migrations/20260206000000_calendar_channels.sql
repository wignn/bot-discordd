
CREATE TABLE IF NOT EXISTS calendar_channels (
    id BIGSERIAL PRIMARY KEY,
    channel_id BIGINT NOT NULL,
    guild_id BIGINT NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    mention_everyone BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS calendar_events_sent (
    id BIGSERIAL PRIMARY KEY,
    event_id TEXT UNIQUE NOT NULL,
    event_title TEXT NOT NULL,
    sent_at BIGINT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_calendar_event_id ON calendar_events_sent(event_id);
