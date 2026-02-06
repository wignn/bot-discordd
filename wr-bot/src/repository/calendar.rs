use sqlx::PgPool;

#[derive(Debug, Clone, sqlx::FromRow)]
pub struct CalendarChannel {
    pub id: i64,
    pub channel_id: i64,
    pub guild_id: i64,
    pub is_active: bool,
    pub mention_everyone: bool,
}

pub struct CalendarRepository;

impl CalendarRepository {
    pub async fn insert_channel(
        pool: &PgPool,
        guild_id: u64,
        channel_id: u64,
    ) -> Result<(), sqlx::Error> {
        sqlx::query!(
            r#"
            INSERT INTO calendar_channels (guild_id, channel_id, is_active, mention_everyone)
            VALUES ($1, $2, TRUE, FALSE)
            ON CONFLICT(guild_id) DO UPDATE SET channel_id = $2, is_active = TRUE
            "#,
            guild_id as i64,
            channel_id as i64,
        )
        .execute(pool)
        .await?;

        Ok(())
    }

    pub async fn disable_channel(pool: &PgPool, guild_id: u64) -> Result<(), sqlx::Error> {
        sqlx::query!(
            "UPDATE calendar_channels SET is_active = FALSE WHERE guild_id = $1",
            guild_id as i64,
        )
        .execute(pool)
        .await?;

        Ok(())
    }

    pub async fn enable_channel(pool: &PgPool, guild_id: u64) -> Result<(), sqlx::Error> {
        sqlx::query!(
            "UPDATE calendar_channels SET is_active = TRUE WHERE guild_id = $1",
            guild_id as i64,
        )
        .execute(pool)
        .await?;

        Ok(())
    }

    pub async fn set_mention_everyone(
        pool: &PgPool,
        guild_id: u64,
        mention: bool,
    ) -> Result<(), sqlx::Error> {
        sqlx::query!(
            "UPDATE calendar_channels SET mention_everyone = $2 WHERE guild_id = $1",
            guild_id as i64,
            mention,
        )
        .execute(pool)
        .await?;

        Ok(())
    }

    pub async fn get_active_channels(pool: &PgPool) -> Result<Vec<CalendarChannel>, sqlx::Error> {
        let channels = sqlx::query_as!(
            CalendarChannel,
            "SELECT id, channel_id, guild_id, is_active, mention_everyone FROM calendar_channels WHERE is_active = TRUE"
        )
        .fetch_all(pool)
        .await?;

        Ok(channels)
    }

    pub async fn get_channel(
        pool: &PgPool,
        guild_id: u64,
    ) -> Result<Option<CalendarChannel>, sqlx::Error> {
        let channel = sqlx::query_as!(
            CalendarChannel,
            "SELECT id, channel_id, guild_id, is_active, mention_everyone FROM calendar_channels WHERE guild_id = $1",
            guild_id as i64,
        )
        .fetch_optional(pool)
        .await?;

        Ok(channel)
    }

    pub async fn is_event_sent(pool: &PgPool, event_id: &str) -> Result<bool, sqlx::Error> {
        let count = sqlx::query_scalar!(
            r#"SELECT COUNT(*) as "count!" FROM calendar_events_sent WHERE event_id = $1"#,
            event_id,
        )
        .fetch_one(pool)
        .await?;

        Ok(count > 0)
    }

    pub async fn insert_event(
        pool: &PgPool,
        event_id: &str,
        event_title: &str,
    ) -> Result<(), sqlx::Error> {
        let now = chrono::Utc::now().timestamp();
        sqlx::query!(
            r#"
            INSERT INTO calendar_events_sent (event_id, event_title, sent_at)
            VALUES ($1, $2, $3)
            ON CONFLICT(event_id) DO NOTHING
            "#,
            event_id,
            event_title,
            now,
        )
        .execute(pool)
        .await?;

        Ok(())
    }

    pub async fn cleanup_old_events(pool: &PgPool, days: i64) -> Result<u64, sqlx::Error> {
        let cutoff = chrono::Utc::now().timestamp() - (days * 86400);
        let result = sqlx::query!(
            "DELETE FROM calendar_events_sent WHERE sent_at < $1",
            cutoff
        )
        .execute(pool)
        .await?;

        Ok(result.rows_affected())
    }
}
