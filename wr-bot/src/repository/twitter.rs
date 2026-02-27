use sqlx::PgPool;
use sqlx::Row;

#[derive(Debug, Clone)]
pub struct TwitterChannel {
    pub id: i64,
    pub channel_id: i64,
    pub guild_id: i64,
    pub is_active: bool,
}

pub struct TwitterRepository;

impl TwitterRepository {
    pub async fn insert_channel(
        pool: &PgPool,
        guild_id: u64,
        channel_id: u64,
    ) -> Result<(), sqlx::Error> {
        sqlx::query(
            r#"
            INSERT INTO twitter_channels (guild_id, channel_id, is_active)
            VALUES ($1, $2, TRUE)
            ON CONFLICT(guild_id) DO UPDATE SET channel_id = $2, is_active = TRUE
            "#,
        )
        .bind(guild_id as i64)
        .bind(channel_id as i64)
        .execute(pool)
        .await?;

        Ok(())
    }

    pub async fn disable_channel(pool: &PgPool, guild_id: u64) -> Result<(), sqlx::Error> {
        sqlx::query("UPDATE twitter_channels SET is_active = FALSE WHERE guild_id = $1")
            .bind(guild_id as i64)
            .execute(pool)
            .await?;

        Ok(())
    }

    pub async fn enable_channel(pool: &PgPool, guild_id: u64) -> Result<(), sqlx::Error> {
        sqlx::query("UPDATE twitter_channels SET is_active = TRUE WHERE guild_id = $1")
            .bind(guild_id as i64)
            .execute(pool)
            .await?;

        Ok(())
    }

    pub async fn get_active_channels(pool: &PgPool) -> Result<Vec<TwitterChannel>, sqlx::Error> {
        let rows = sqlx::query(
            "SELECT id, channel_id, guild_id, is_active FROM twitter_channels WHERE is_active = TRUE",
        )
        .fetch_all(pool)
        .await?;

        let channels = rows
            .iter()
            .map(|row| TwitterChannel {
                id: row.get("id"),
                channel_id: row.get("channel_id"),
                guild_id: row.get("guild_id"),
                is_active: row.get("is_active"),
            })
            .collect();

        Ok(channels)
    }

    pub async fn get_channel(
        pool: &PgPool,
        guild_id: u64,
    ) -> Result<Option<TwitterChannel>, sqlx::Error> {
        let row = sqlx::query(
            "SELECT id, channel_id, guild_id, is_active FROM twitter_channels WHERE guild_id = $1",
        )
        .bind(guild_id as i64)
        .fetch_optional(pool)
        .await?;

        Ok(row.map(|r| TwitterChannel {
            id: r.get("id"),
            channel_id: r.get("channel_id"),
            guild_id: r.get("guild_id"),
            is_active: r.get("is_active"),
        }))
    }

    pub async fn is_tweet_sent(pool: &PgPool, tweet_id: &str) -> Result<bool, sqlx::Error> {
        let row = sqlx::query(r#"SELECT COUNT(*) as count FROM twitter_sent WHERE tweet_id = $1"#)
            .bind(tweet_id)
            .fetch_one(pool)
            .await?;

        let count: i64 = row.get("count");
        Ok(count > 0)
    }

    pub async fn insert_tweet(
        pool: &PgPool,
        tweet_id: &str,
        author: &str,
    ) -> Result<(), sqlx::Error> {
        let now = chrono::Utc::now().timestamp();
        sqlx::query(
            r#"
            INSERT INTO twitter_sent (tweet_id, author, sent_at)
            VALUES ($1, $2, $3)
            ON CONFLICT(tweet_id) DO NOTHING
            "#,
        )
        .bind(tweet_id)
        .bind(author)
        .bind(now)
        .execute(pool)
        .await?;

        Ok(())
    }

    pub async fn cleanup_old_tweets(pool: &PgPool, days: i64) -> Result<u64, sqlx::Error> {
        let cutoff = chrono::Utc::now().timestamp() - (days * 86400);
        let result = sqlx::query("DELETE FROM twitter_sent WHERE sent_at < $1")
            .bind(cutoff)
            .execute(pool)
            .await?;

        Ok(result.rows_affected())
    }
}
