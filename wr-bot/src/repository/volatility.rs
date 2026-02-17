use sqlx::PgPool;

#[derive(Debug, Clone, sqlx::FromRow)]
pub struct VolatilityChannel {
    pub id: i64,
    pub channel_id: i64,
    pub guild_id: i64,
    pub is_active: bool,
}

pub struct VolatilityRepository;

impl VolatilityRepository {
    pub async fn insert_channel(
        pool: &PgPool,
        guild_id: u64,
        channel_id: u64,
    ) -> Result<(), sqlx::Error> {
        sqlx::query!(
            r#"
            INSERT INTO volatility_channels (guild_id, channel_id, is_active)
            VALUES ($1, $2, TRUE)
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
            "UPDATE volatility_channels SET is_active = FALSE WHERE guild_id = $1",
            guild_id as i64,
        )
        .execute(pool)
        .await?;

        Ok(())
    }

    pub async fn get_active_channels(pool: &PgPool) -> Result<Vec<VolatilityChannel>, sqlx::Error> {
        let channels = sqlx::query_as!(
            VolatilityChannel,
            "SELECT id, channel_id, guild_id, is_active FROM volatility_channels WHERE is_active = TRUE"
        )
        .fetch_all(pool)
        .await?;

        Ok(channels)
    }

    pub async fn get_channel(
        pool: &PgPool,
        guild_id: u64,
    ) -> Result<Option<VolatilityChannel>, sqlx::Error> {
        let channel = sqlx::query_as!(
            VolatilityChannel,
            "SELECT id, channel_id, guild_id, is_active FROM volatility_channels WHERE guild_id = $1",
            guild_id as i64,
        )
        .fetch_optional(pool)
        .await?;

        Ok(channel)
    }
}
