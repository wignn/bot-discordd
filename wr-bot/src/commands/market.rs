use crate::commands::Data;
use crate::repository::PriceAlertRepository;
use crate::services::{market_ws, price_alert};
use poise::serenity_prelude::CreateEmbed;

type Error = Box<dyn std::error::Error + Send + Sync>;
type Context<'a> = poise::Context<'a, Data, Error>;

const MAX_ALERTS_PER_USER: i64 = 10;

#[poise::command(prefix_command, slash_command, rename = "price")]
pub async fn price(
    ctx: Context<'_>,
    #[description = "Symbol to check (e.g. XAUUSD, BTCUSDT)"] symbol: String,
) -> Result<(), Error> {
    let upper = symbol.to_uppercase();

    match market_ws::get_price(&upper) {
        Some(cached) => {
            let (color, arrow) = match cached.direction.as_str() {
                "buy" => (0x34D399u32, "BUY"),
                "sell" => (0xF87171u32, "SELL"),
                _ => (0x60A5FAu32, "BUY"),
            };

            let asset_label = match cached.asset_type.as_str() {
                "crypto" => "Crypto",
                "forex" => "Forex",
                "stock" => "Stock",
                _ => "Market",
            };

            let price_display = if cached.asset_type == "crypto" {
                format!("${}", cached.price_str)
            } else {
                cached.price_str.clone()
            };

            let elapsed = cached.updated_at.elapsed();
            let ago = if elapsed.as_secs() < 60 {
                format!("{}s ago", elapsed.as_secs())
            } else {
                format!("{}m ago", elapsed.as_secs() / 60)
            };

            let embed = CreateEmbed::new()
                .title(format!("{} {} Price", arrow, upper))
                .description(format!("## {}", price_display))
                .field("Type", asset_label, true)
                .field("Direction", &cached.direction, true)
                .field("Updated", &ago, true)
                .color(color)
                .footer(poise::serenity_prelude::CreateEmbedFooter::new(
                    "Fio • Powered by MT5",
                ))
                .timestamp(poise::serenity_prelude::Timestamp::now());

            ctx.send(poise::CreateReply::default().embed(embed)).await?;
        }
        None => {
            let available = market_ws::get_all_prices();
            let symbols: Vec<String> = available.iter().map(|p| p.symbol.clone()).collect();

            let desc = if symbols.is_empty() {
                "No market data available yet. Please wait for the market feed to initialize."
                    .to_string()
            } else {
                format!(
                    "Symbol `{}` not found.\n\n**Available symbols:**\n{}",
                    upper,
                    symbols
                        .iter()
                        .map(|s| format!("`{}`", s))
                        .collect::<Vec<_>>()
                        .join(" • ")
                )
            };

            let embed = CreateEmbed::new()
                .title("Symbol Not Found")
                .description(desc)
                .color(0xF39C12u32)
                .footer(poise::serenity_prelude::CreateEmbedFooter::new("Fio"));

            ctx.send(poise::CreateReply::default().embed(embed)).await?;
        }
    }

    Ok(())
}

/// Show all current market prices
#[poise::command(prefix_command, slash_command, rename = "prices")]
pub async fn prices(ctx: Context<'_>) -> Result<(), Error> {
    let all = market_ws::get_all_prices();

    if all.is_empty() {
        let embed = CreateEmbed::new()
            .title("Market Prices")
            .description("No market data available yet. Please wait for the feed to initialize.")
            .color(0xF39C12u32)
            .footer(poise::serenity_prelude::CreateEmbedFooter::new("Fio"));

        ctx.send(poise::CreateReply::default().embed(embed)).await?;
        return Ok(());
    }

    let mut forex_lines = Vec::new();
    let mut crypto_lines = Vec::new();
    let mut stock_lines = Vec::new();

    let mut sorted = all.clone();
    sorted.sort_by(|a, b| a.symbol.cmp(&b.symbol));

    for p in &sorted {
        let arrow = match p.direction.as_str() {
            "buy" => "🟢",
            "sell" => "🔴",
            _ => "⚪",
        };

        let line = if p.asset_type == "crypto" {
            format!("{} **{}** — ${}", arrow, p.symbol, p.price_str)
        } else {
            format!("{} **{}** — {}", arrow, p.symbol, p.price_str)
        };

        if p.asset_type == "crypto" {
            crypto_lines.push(line);
        } else if p.asset_type == "stock" {
            stock_lines.push(line);
        } else {
            forex_lines.push(line);
        }
    }

    let mut embed = CreateEmbed::new()
        .title("Live Market Prices")
        .color(0x8B5CF6u32)
        .footer(poise::serenity_prelude::CreateEmbedFooter::new(
            "Fio • Powered by Infoway",
        ))
        .timestamp(poise::serenity_prelude::Timestamp::now());

    if !forex_lines.is_empty() {
        embed = embed.field("Forex", forex_lines.join("\n"), false);
    }
    if !crypto_lines.is_empty() {
        embed = embed.field("Crypto", crypto_lines.join("\n"), false);
    }
    if !stock_lines.is_empty() {
        embed = embed.field("Stocks", stock_lines.join("\n"), false);
    }

    ctx.send(poise::CreateReply::default().embed(embed)).await?;

    Ok(())
}

/// Set a price alert -- get notified via DM when price is reached
#[poise::command(slash_command, rename = "alert")]
pub async fn alert(
    ctx: Context<'_>,
    #[description = "Symbol (e.g. XAUUSD, BTCUSDT)"] symbol: String,
    #[description = "Target price"] target_price: f64,
) -> Result<(), Error> {
    let upper = symbol.to_uppercase();
    let db = &ctx.data().db;
    let user_id = ctx.author().id.get();
    let guild_id = ctx.guild_id().map(|g| g.get()).unwrap_or(0);

    let current = match market_ws::get_price(&upper) {
        Some(cached) => cached,
        None => {
            let available = market_ws::get_all_prices();
            let symbols: Vec<String> = available.iter().map(|p| p.symbol.clone()).collect();

            let desc = if symbols.is_empty() {
                "No market data available yet. Please wait for the market feed to initialize."
                    .to_string()
            } else {
                format!(
                    "Symbol `{}` not found.\n\n**Available symbols:**\n{}",
                    upper,
                    symbols
                        .iter()
                        .map(|s| format!("`{}`", s))
                        .collect::<Vec<_>>()
                        .join(" • ")
                )
            };

            let embed = CreateEmbed::new()
                .title("Symbol Not Found")
                .description(desc)
                .color(0xF39C12u32)
                .footer(poise::serenity_prelude::CreateEmbedFooter::new("Fio"));

            ctx.send(poise::CreateReply::default().embed(embed)).await?;
            return Ok(());
        }
    };

    let count = PriceAlertRepository::count_user_alerts(db, user_id).await?;
    if count >= MAX_ALERTS_PER_USER {
        let embed = CreateEmbed::new()
            .title("Limit Tercapai")
            .description(format!(
                "Kamu sudah punya {} alert aktif. Maksimal {} alert.\nHapus alert yang tidak diperlukan dengan `/alert_remove`.",
                count, MAX_ALERTS_PER_USER
            ))
            .color(0xF39C12u32)
            .footer(poise::serenity_prelude::CreateEmbedFooter::new("Fio"));

        ctx.send(poise::CreateReply::default().embed(embed)).await?;
        return Ok(());
    }

    let direction = if target_price > current.price {
        "above"
    } else if target_price < current.price {
        "below"
    } else {
        let embed = CreateEmbed::new()
            .title("Invalid Target")
            .description("Target price tidak boleh sama dengan harga saat ini.")
            .color(0xF39C12u32)
            .footer(poise::serenity_prelude::CreateEmbedFooter::new("Fio"));

        ctx.send(poise::CreateReply::default().embed(embed)).await?;
        return Ok(());
    };

    let created =
        PriceAlertRepository::create_alert(db, user_id, guild_id, &upper, target_price, direction)
            .await?;

    price_alert::add_to_cache(&created);

    let current_display = if current.asset_type == "crypto" {
        format!("${}", current.price_str)
    } else {
        current.price_str.clone()
    };

    let target_display = if current.asset_type == "crypto" {
        format!("${:.2}", target_price)
    } else {
        format!("{:.5}", target_price)
    };

    let direction_label = if direction == "above" {
        "naik di atas"
    } else {
        "turun di bawah"
    };

    let embed = CreateEmbed::new()
        .title("Price Alert Aktif")
        .description(format!(
            "Alert akan dikirim via DM ketika **{}** {} **{}**",
            upper, direction_label, target_display
        ))
        .field("Symbol", &upper, true)
        .field("Harga Saat Ini", &current_display, true)
        .field("Target", &target_display, true)
        .field("Direction", direction, true)
        .field("Alert ID", &format!("#{}", created.id), true)
        .color(0x8B5CF6u32)
        .footer(poise::serenity_prelude::CreateEmbedFooter::new(
            "Fio Price Alert",
        ))
        .timestamp(poise::serenity_prelude::Timestamp::now());

    ctx.send(poise::CreateReply::default().embed(embed)).await?;

    Ok(())
}

/// Show all your active price alerts
#[poise::command(slash_command, rename = "alerts")]
pub async fn alerts(ctx: Context<'_>) -> Result<(), Error> {
    let db = &ctx.data().db;
    let user_id = ctx.author().id.get();

    let user_alerts = PriceAlertRepository::get_user_alerts(db, user_id).await?;

    if user_alerts.is_empty() {
        let embed = CreateEmbed::new()
            .title("Price Alerts")
            .description("Kamu belum punya alert aktif.\nGunakan `/alert <symbol> <target>` untuk membuat alert.")
            .color(0x60A5FAu32)
            .footer(poise::serenity_prelude::CreateEmbedFooter::new("Fio"));

        ctx.send(poise::CreateReply::default().embed(embed)).await?;
        return Ok(());
    }

    let mut lines = Vec::new();
    for a in &user_alerts {
        let dir_icon = if a.direction == "above" { "⬆" } else { "⬇" };
        let current = market_ws::get_price(&a.symbol);
        let current_str = current
            .map(|c| {
                if c.asset_type == "crypto" {
                    format!("${}", c.price_str)
                } else {
                    c.price_str
                }
            })
            .unwrap_or_else(|| "-".to_string());

        let target_str = if market_ws::get_price(&a.symbol)
            .map(|c| c.asset_type == "crypto")
            .unwrap_or(false)
        {
            format!("${:.2}", a.target_price)
        } else {
            format!("{:.5}", a.target_price)
        };

        lines.push(format!(
            "`#{}` {} **{}** {} {} (now: {})",
            a.id, dir_icon, a.symbol, a.direction, target_str, current_str
        ));
    }

    let embed = CreateEmbed::new()
        .title(format!(
            "Price Alerts ({}/{})",
            user_alerts.len(),
            MAX_ALERTS_PER_USER
        ))
        .description(lines.join("\n"))
        .color(0x8B5CF6u32)
        .footer(poise::serenity_prelude::CreateEmbedFooter::new(
            "Hapus alert dengan /alert_remove <id>",
        ))
        .timestamp(poise::serenity_prelude::Timestamp::now());

    ctx.send(poise::CreateReply::default().embed(embed)).await?;

    Ok(())
}

/// Remove a price alert by ID
#[poise::command(slash_command, rename = "alert_remove")]
pub async fn alert_remove(
    ctx: Context<'_>,
    #[description = "Alert ID to remove"] alert_id: i64,
) -> Result<(), Error> {
    let db = &ctx.data().db;
    let user_id = ctx.author().id.get();

    let deleted = PriceAlertRepository::delete_alert(db, alert_id, user_id).await?;

    if deleted {
        price_alert::remove_from_cache(alert_id);
    }

    let embed = if deleted {
        CreateEmbed::new()
            .title("Alert Dihapus")
            .description(format!("Alert `#{}` berhasil dihapus.", alert_id))
            .color(0x34D399u32)
            .footer(poise::serenity_prelude::CreateEmbedFooter::new("Fio"))
    } else {
        CreateEmbed::new()
            .title("Alert Tidak Ditemukan")
            .description(format!(
                "Alert `#{}` tidak ditemukan atau bukan milikmu.",
                alert_id
            ))
            .color(0xF39C12u32)
            .footer(poise::serenity_prelude::CreateEmbedFooter::new("Fio"))
    };

    ctx.send(poise::CreateReply::default().embed(embed)).await?;

    Ok(())
}
