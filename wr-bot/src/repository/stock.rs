use sqlx::PgPool;

#[derive(Debug, Clone, sqlx::FromRow)]
pub struct StockChannel {
    pub id: i64,
    pub channel_id: i64,
    pub guild_id: i64,
    pub tickers_filter: Option<String>,
    pub min_impact: Option<String>,
    pub categories: Option<String>,
    pub mention_everyone: bool,
    pub is_active: bool,
}

pub struct StockRepository;

impl StockRepository {
    pub async fn insert_channel(
        pool: &PgPool,
        guild_id: u64,
        channel_id: u64,
    ) -> Result<(), sqlx::Error> {
        sqlx::query!(
            r#"
            INSERT INTO stock_news_channels (guild_id, channel_id, is_active)
            VALUES ($1, $2, TRUE)
            ON CONFLICT(channel_id) DO UPDATE SET guild_id = $1, is_active = TRUE
            "#,
            guild_id as i64,
            channel_id as i64,
        )
        .execute(pool)
        .await?;

        Ok(())
    }

    pub async fn disable_channel(pool: &PgPool, channel_id: u64) -> Result<(), sqlx::Error> {
        sqlx::query!(
            "UPDATE stock_news_channels SET is_active = FALSE WHERE channel_id = $1",
            channel_id as i64,
        )
        .execute(pool)
        .await?;

        Ok(())
    }

    pub async fn get_active_channels(pool: &PgPool) -> Result<Vec<StockChannel>, sqlx::Error> {
        let channels = sqlx::query_as!(
            StockChannel,
            r#"SELECT id, channel_id, guild_id, tickers_filter, min_impact, 
                      categories, mention_everyone, is_active 
               FROM stock_news_channels 
               WHERE is_active = TRUE"#
        )
        .fetch_all(pool)
        .await?;

        Ok(channels)
    }

    pub async fn get_channel(
        pool: &PgPool,
        channel_id: u64,
    ) -> Result<Option<StockChannel>, sqlx::Error> {
        let channel = sqlx::query_as!(
            StockChannel,
            r#"SELECT id, channel_id, guild_id, tickers_filter, min_impact, 
                      categories, mention_everyone, is_active 
               FROM stock_news_channels 
               WHERE channel_id = $1"#,
            channel_id as i64,
        )
        .fetch_optional(pool)
        .await?;

        Ok(channel)
    }

    pub async fn is_stock_news_sent(pool: &PgPool, news_id: &str) -> Result<bool, sqlx::Error> {
        let prefixed_id = format!("stock_{}", news_id);
        let count = sqlx::query_scalar!(
            r#"SELECT COUNT(*) as "count!" FROM forex_news_sent WHERE news_id = $1"#,
            prefixed_id,
        )
        .fetch_one(pool)
        .await?;

        Ok(count > 0)
    }

    pub async fn insert_stock_news(
        pool: &PgPool,
        news_id: &str,
        source: &str,
    ) -> Result<(), sqlx::Error> {
        let prefixed_id = format!("stock_{}", news_id);
        let now = chrono::Utc::now().timestamp();
        sqlx::query!(
            r#"
            INSERT INTO forex_news_sent (news_id, source, sent_at)
            VALUES ($1, $2, $3)
            ON CONFLICT(news_id) DO NOTHING
            "#,
            prefixed_id,
            source,
            now,
        )
        .execute(pool)
        .await?;

        Ok(())
    }
}
