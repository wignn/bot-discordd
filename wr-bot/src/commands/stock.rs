use crate::commands::Data;
use poise::serenity_prelude::{CreateEmbed, CreateEmbedFooter};

type Error = Box<dyn std::error::Error + Send + Sync>;
type Context<'a> = poise::Context<'a, Data, Error>;

/// Stock news commands
#[poise::command(
    slash_command,
    subcommands("subscribe", "unsubscribe", "status", "latest"),
    subcommand_required
)]
pub async fn stocknews(_ctx: Context<'_>) -> Result<(), Error> {
    Ok(())
}

/// Subscribe this channel to Indonesian stock news alerts
#[poise::command(slash_command, required_permissions = "MANAGE_CHANNELS")]
pub async fn subscribe(
    ctx: Context<'_>,
    #[description = "Mention @everyone for high impact news"] mention_everyone: Option<bool>,
) -> Result<(), Error> {
    let pool = ctx.data().db.as_ref();
    
    let channel_id = ctx.channel_id().get() as i64;
    let guild_id = ctx.guild_id().map(|g| g.get() as i64).unwrap_or(0);
    let mention = mention_everyone.unwrap_or(false);
    
    sqlx::query(
        r#"
        INSERT INTO stock_news_channels (channel_id, guild_id, mention_everyone, is_active)
        VALUES ($1, $2, $3, TRUE)
        ON CONFLICT (channel_id) DO UPDATE
        SET mention_everyone = $3, is_active = TRUE, updated_at = NOW()
        "#,
    )
    .bind(channel_id)
    .bind(guild_id)
    .bind(mention)
    .execute(pool)
    .await?;
    
    let embed = CreateEmbed::new()
        .title("Stock News Alert Aktif")
        .description("Channel ini sekarang menerima alert berita saham Indonesia.")
        .field("Sumber", "CNBC Indonesia, Kontan, Bisnis Indonesia, Detik Finance, IDX Channel", false)
        .field("Mention Everyone", if mention { "Ya (untuk high impact)" } else { "Tidak" }, true)
        .color(0x00FF00)
        .footer(CreateEmbedFooter::new("Gunakan /stocknews unsubscribe untuk berhenti"));
    
    ctx.send(poise::CreateReply::default().embed(embed)).await?;
    Ok(())
}

/// Unsubscribe this channel from stock news alerts
#[poise::command(slash_command, required_permissions = "MANAGE_CHANNELS")]
pub async fn unsubscribe(ctx: Context<'_>) -> Result<(), Error> {
    let pool = ctx.data().db.as_ref();
    
    let channel_id = ctx.channel_id().get() as i64;
    
    let result = sqlx::query(
        "UPDATE stock_news_channels SET is_active = FALSE, updated_at = NOW() WHERE channel_id = $1",
    )
    .bind(channel_id)
    .execute(pool)
    .await?;
    
    let embed = if result.rows_affected() > 0 {
        CreateEmbed::new()
            .title("Stock News Alert Dinonaktifkan")
            .description("Channel ini tidak akan menerima alert berita saham lagi.")
            .color(0xFF6600)
    } else {
        CreateEmbed::new()
            .title("Tidak Ada Langganan")
            .description("Channel ini tidak berlangganan stock news alert.")
            .color(0xFF0000)
    };
    
    ctx.send(poise::CreateReply::default().embed(embed)).await?;
    Ok(())
}

/// Check stock news subscription status
#[poise::command(slash_command)]
pub async fn status(ctx: Context<'_>) -> Result<(), Error> {
    let pool = ctx.data().db.as_ref();
    
    let channel_id = ctx.channel_id().get() as i64;
    
    let subscription: Option<(bool, bool, chrono::NaiveDateTime)> = sqlx::query_as(
        "SELECT is_active, mention_everyone, created_at FROM stock_news_channels WHERE channel_id = $1",
    )
    .bind(channel_id)
    .fetch_optional(pool)
    .await?;
    
    let embed = match subscription {
        Some((is_active, mention, created_at)) if is_active => {
            CreateEmbed::new()
                .title("Stock News Alert Status")
                .field("Status", "Aktif", true)
                .field("Mention Everyone", if mention { "Ya" } else { "Tidak" }, true)
                .field("Aktif Sejak", created_at.format("%Y-%m-%d %H:%M").to_string(), false)
                .color(0x00FF00)
        }
        _ => {
            CreateEmbed::new()
                .title("Stock News Alert Status")
                .description("Channel ini tidak berlangganan stock news alert.")
                .field("Aktifkan", "Gunakan `/stocknews subscribe`", false)
                .color(0x808080)
        }
    };
    
    ctx.send(poise::CreateReply::default().embed(embed)).await?;
    Ok(())
}

/// Get latest Indonesian stock news
#[poise::command(slash_command)]
pub async fn latest(
    ctx: Context<'_>,
    #[description = "Filter by ticker (e.g. BBCA, BBRI)"] ticker: Option<String>,
    #[description = "Number of news to show (max 10)"] limit: Option<i64>,
) -> Result<(), Error> {
    ctx.defer().await?;
    
    let pool = ctx.data().db.as_ref();
    let limit = limit.unwrap_or(5).min(10);
    
    // Query latest stock news
    let rows: Vec<(String, String, Option<String>, Option<String>, String, Option<String>, Option<String>, Option<String>, Option<chrono::NaiveDateTime>)> = if let Some(ticker) = ticker {
        let ticker_upper = ticker.to_uppercase();
        sqlx::query_as(
            r#"
            SELECT content_hash, title, summary, source_name, original_url, category, sentiment, impact_level, published_at
            FROM stock_news
            WHERE is_processed = TRUE AND $1 = ANY(string_to_array(tickers, ','))
            ORDER BY published_at DESC NULLS LAST
            LIMIT $2
            "#,
        )
        .bind(ticker_upper)
        .bind(limit)
        .fetch_all(pool)
        .await?
    } else {
        sqlx::query_as(
            r#"
            SELECT content_hash, title, summary, source_name, original_url, category, sentiment, impact_level, published_at
            FROM stock_news
            WHERE is_processed = TRUE
            ORDER BY published_at DESC NULLS LAST
            LIMIT $1
            "#,
        )
        .bind(limit)
        .fetch_all(pool)
        .await?
    };
    
    if rows.is_empty() {
        let embed = CreateEmbed::new()
            .title("Tidak Ada Berita")
            .description("Belum ada berita saham Indonesia yang tersedia.")
            .color(0x808080);
        ctx.send(poise::CreateReply::default().embed(embed)).await?;
        return Ok(());
    }
    
    // Build embed with news list
    let mut description = String::new();
    
    for (i, (_, title, _summary, source_name, url, _category, sentiment, _impact, published_at)) in rows.iter().enumerate() {
        let sentiment_icon = match sentiment.as_deref() {
            Some("bullish") => "+",
            Some("bearish") => "-",
            _ => " ",
        };
        
        let time_str = published_at
            .map(|t| t.format("%H:%M").to_string())
            .unwrap_or_default();
        
        description.push_str(&format!(
            "**{}. [{}]({})** {}\n{} | {}\n\n",
            i + 1,
            title,
            url,
            sentiment_icon,
            source_name.as_deref().unwrap_or("Unknown"),
            time_str
        ));
    }
    
    let embed = CreateEmbed::new()
        .title("Berita Saham Indonesia Terbaru")
        .description(description)
        .color(0x2962FF)
        .footer(CreateEmbedFooter::new("Data dari CNBC Indonesia, Kontan, Bisnis Indonesia, dll"));
    
    ctx.send(poise::CreateReply::default().embed(embed)).await?;
    Ok(())
}

/// Search stock news by keyword
#[poise::command(slash_command)]
pub async fn search(
    ctx: Context<'_>,
    #[description = "Keyword to search"] keyword: String,
    #[description = "Number of results (max 10)"] limit: Option<i64>,
) -> Result<(), Error> {
    ctx.defer().await?;
    
    let pool = ctx.data().db.as_ref();
    let limit = limit.unwrap_or(5).min(10);
    let search_pattern = format!("%{}%", keyword);
    
    let rows: Vec<(String, String, Option<String>, Option<String>, String)> = sqlx::query_as(
        r#"
        SELECT content_hash, title, summary, source_name, original_url
        FROM stock_news
        WHERE is_processed = TRUE AND (title ILIKE $1 OR summary ILIKE $1)
        ORDER BY published_at DESC NULLS LAST
        LIMIT $2
        "#,
    )
    .bind(&search_pattern)
    .bind(limit)
    .fetch_all(pool)
    .await?;
    
    if rows.is_empty() {
        let embed = CreateEmbed::new()
            .title("Tidak Ditemukan")
            .description(format!("Tidak ada berita dengan keyword \"{}\"", keyword))
            .color(0x808080);
        ctx.send(poise::CreateReply::default().embed(embed)).await?;
        return Ok(());
    }
    
    let mut description = String::new();
    
    for (i, (_, title, summary, _source, url)) in rows.iter().enumerate() {
        description.push_str(&format!(
            "**{}. [{}]({})**\n{}\n\n",
            i + 1,
            title,
            url,
            summary.as_deref().unwrap_or("").chars().take(150).collect::<String>()
        ));
    }
    
    let embed = CreateEmbed::new()
        .title(format!("Hasil Pencarian: {}", keyword))
        .description(description)
        .color(0x2962FF);
    
    ctx.send(poise::CreateReply::default().embed(embed)).await?;
    Ok(())
}

/// Get stock market summary
#[poise::command(slash_command)]
pub async fn market(ctx: Context<'_>) -> Result<(), Error> {
    ctx.defer().await?;
    
    let pool = ctx.data().db.as_ref();
    
    // Get recent high impact news
    let high_impact: Vec<(String, Option<String>)> = sqlx::query_as(
        r#"
        SELECT title, sentiment
        FROM stock_news
        WHERE is_processed = TRUE AND impact_level = 'high'
        AND published_at > NOW() - INTERVAL '24 hours'
        ORDER BY published_at DESC
        LIMIT 5
        "#,
    )
    .fetch_all(pool)
    .await?;
    
    // Get sentiment distribution
    let sentiment_stats: Vec<(Option<String>, i64)> = sqlx::query_as(
        r#"
        SELECT sentiment, COUNT(*) as count
        FROM stock_news
        WHERE is_processed = TRUE
        AND published_at > NOW() - INTERVAL '24 hours'
        GROUP BY sentiment
        "#,
    )
    .fetch_all(pool)
    .await?;
    
    let mut bullish = 0i64;
    let mut bearish = 0i64;
    let mut neutral = 0i64;
    
    for (sentiment, count) in &sentiment_stats {
        match sentiment.as_deref() {
            Some("bullish") => bullish = *count,
            Some("bearish") => bearish = *count,
            _ => neutral = *count,
        }
    }
    
    let total = bullish + bearish + neutral;
    let sentiment_indicator = if total > 0 {
        let bullish_pct = (bullish * 100) / total;
        let bearish_pct = (bearish * 100) / total;
        if bullish_pct > 60 {
            "Bullish"
        } else if bearish_pct > 60 {
            "Bearish"
        } else {
            "Netral"
        }
    } else {
        "N/A"
    };
    
    // Build high impact news list
    let high_impact_list = if high_impact.is_empty() {
        "Tidak ada berita high impact dalam 24 jam terakhir".to_string()
    } else {
        high_impact.iter()
            .map(|(title, sentiment)| {
                let icon = match sentiment.as_deref() {
                    Some("bullish") => "+",
                    Some("bearish") => "-",
                    _ => " ",
                };
                format!("{} {}", icon, title)
            })
            .collect::<Vec<_>>()
            .join("\n")
    };
    
    let embed = CreateEmbed::new()
        .title("Ringkasan Pasar Saham Indonesia")
        .field("Sentimen 24 Jam", sentiment_indicator, true)
        .field("Bullish", bullish.to_string(), true)
        .field("Bearish", bearish.to_string(), true)
        .field("Berita High Impact (24 Jam)", high_impact_list, false)
        .color(match sentiment_indicator {
            "Bullish" => 0x00FF00,
            "Bearish" => 0xFF0000,
            _ => 0x808080,
        })
        .footer(CreateEmbedFooter::new("Update setiap 3 menit"));
    
    ctx.send(poise::CreateReply::default().embed(embed)).await?;
    Ok(())
}
