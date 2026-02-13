use crate::commands::Data;
use crate::services::market_ws;
use poise::serenity_prelude::CreateEmbed;

type Error = Box<dyn std::error::Error + Send + Sync>;
type Context<'a> = poise::Context<'a, Data, Error>;

/// Check real-time price for a forex/crypto symbol
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
                    "Fio • Powered by Infoway",
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
            .title("📊 Market Prices")
            .description("No market data available yet. Please wait for the feed to initialize.")
            .color(0xF39C12u32)
            .footer(poise::serenity_prelude::CreateEmbedFooter::new("Fio"));

        ctx.send(poise::CreateReply::default().embed(embed)).await?;
        return Ok(());
    }

    let mut forex_lines = Vec::new();
    let mut crypto_lines = Vec::new();

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
        } else {
            forex_lines.push(line);
        }
    }

    let mut embed = CreateEmbed::new()
        .title("📊 Live Market Prices")
        .color(0x8B5CF6u32)
        .footer(poise::serenity_prelude::CreateEmbedFooter::new(
            "Fio • Powered by Infoway",
        ))
        .timestamp(poise::serenity_prelude::Timestamp::now());

    if !forex_lines.is_empty() {
        embed = embed.field("💹 Forex", forex_lines.join("\n"), false);
    }
    if !crypto_lines.is_empty() {
        embed = embed.field("₿ Crypto", crypto_lines.join("\n"), false);
    }

    ctx.send(poise::CreateReply::default().embed(embed)).await?;

    Ok(())
}
