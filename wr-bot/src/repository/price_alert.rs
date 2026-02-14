use sqlx::PgPool;

#[derive(Debug, Clone, sqlx::FromRow)]
pub struct PriceAlert {
    pub id: i64,
    pub user_id: i64,
    pub guild_id: i64,
    pub symbol: String,
    pub target_price: f64,
    pub direction: String,
    pub is_triggered: bool,
    pub created_at: chrono::DateTime<chrono::Utc>,
    pub triggered_at: Option<chrono::DateTime<chrono::Utc>>,
}

pub struct PriceAlertRepository;

impl PriceAlertRepository {
    pub async fn create_alert(
        pool: &PgPool,
        user_id: u64,
        guild_id: u64,
        symbol: &str,
        target_price: f64,
        direction: &str,
    ) -> Result<PriceAlert, sqlx::Error> {
        let alert = sqlx::query_as!(
            PriceAlert,
            r#"
            INSERT INTO price_alerts (user_id, guild_id, symbol, target_price, direction)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id, user_id, guild_id, symbol, target_price, direction, is_triggered, created_at, triggered_at
            "#,
            user_id as i64,
            guild_id as i64,
            symbol,
            target_price,
            direction,
        )
        .fetch_one(pool)
        .await?;

        Ok(alert)
    }

    pub async fn get_user_alerts(
        pool: &PgPool,
        user_id: u64,
    ) -> Result<Vec<PriceAlert>, sqlx::Error> {
        let alerts = sqlx::query_as!(
            PriceAlert,
            r#"
            SELECT id, user_id, guild_id, symbol, target_price, direction, is_triggered, created_at, triggered_at
            FROM price_alerts
            WHERE user_id = $1 AND is_triggered = FALSE
            ORDER BY created_at DESC
            "#,
            user_id as i64,
        )
        .fetch_all(pool)
        .await?;

        Ok(alerts)
    }

    pub async fn get_active_alerts_by_symbol(
        pool: &PgPool,
        symbol: &str,
    ) -> Result<Vec<PriceAlert>, sqlx::Error> {
        let alerts = sqlx::query_as!(
            PriceAlert,
            r#"
            SELECT id, user_id, guild_id, symbol, target_price, direction, is_triggered, created_at, triggered_at
            FROM price_alerts
            WHERE symbol = $1 AND is_triggered = FALSE
            "#,
            symbol,
        )
        .fetch_all(pool)
        .await?;

        Ok(alerts)
    }

    pub async fn get_all_active_symbols(pool: &PgPool) -> Result<Vec<String>, sqlx::Error> {
        let symbols = sqlx::query_scalar!(
            r#"SELECT DISTINCT symbol FROM price_alerts WHERE is_triggered = FALSE"#
        )
        .fetch_all(pool)
        .await?;

        Ok(symbols)
    }

    pub async fn trigger_alert(pool: &PgPool, alert_id: i64) -> Result<(), sqlx::Error> {
        sqlx::query!(
            r#"
            UPDATE price_alerts
            SET is_triggered = TRUE, triggered_at = NOW()
            WHERE id = $1
            "#,
            alert_id,
        )
        .execute(pool)
        .await?;

        Ok(())
    }

    pub async fn delete_alert(
        pool: &PgPool,
        alert_id: i64,
        user_id: u64,
    ) -> Result<bool, sqlx::Error> {
        let result = sqlx::query!(
            "DELETE FROM price_alerts WHERE id = $1 AND user_id = $2 AND is_triggered = FALSE",
            alert_id,
            user_id as i64,
        )
        .execute(pool)
        .await?;

        Ok(result.rows_affected() > 0)
    }

    pub async fn count_user_alerts(pool: &PgPool, user_id: u64) -> Result<i64, sqlx::Error> {
        let count = sqlx::query_scalar!(
            r#"SELECT COUNT(*) as "count!" FROM price_alerts WHERE user_id = $1 AND is_triggered = FALSE"#,
            user_id as i64,
        )
        .fetch_one(pool)
        .await?;

        Ok(count)
    }
}
