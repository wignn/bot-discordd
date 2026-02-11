-- Migration: Only allow one stock news channel per guild

ALTER TABLE stock_news_channels
    ADD CONSTRAINT unique_guild_id UNIQUE (guild_id);

-- If you want to auto-migrate existing data, you may need to clean up duplicates first:
-- DELETE FROM stock_news_channels a
-- USING stock_news_channels b
-- WHERE a.guild_id = b.guild_id AND a.id < b.id;
