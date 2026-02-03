use crate::commands::Data;
use crate::services::{get_forex_api, get_forex_ws};
use poise::serenity_prelude::{CreateAttachment, CreateEmbed};

type Error = Box<dyn std::error::Error + Send + Sync>;
type Context<'a> = poise::Context<'a, Data, Error>;

async fn send_embed(ctx: Context<'_>, embed: CreateEmbed) -> Result<(), Error> {
    ctx.send(poise::CreateReply::default().embed(embed)).await?;
    Ok(())
}

#[poise::command(slash_command, prefix_command)]
pub async fn fprice(
    ctx: Context<'_>,
    #[description = "Symbol (e.g., xauusd, eurusd, gbpusd)"] symbol: String,
) -> Result<(), Error> {
    let ws_client = match get_forex_ws() {
        Some(c) => c,
        None => {
            send_embed(
                ctx,
                CreateEmbed::new()
                    .title("Error")
                    .description("Forex service not connected")
                    .color(0xff0000),
            )
            .await?;
            return Ok(());
        }
    };

    let symbol_lower = symbol.to_lowercase();

    match ws_client.get_price(&symbol_lower) {
        Some(price) => {
            let embed = CreateEmbed::new()
                .title(format!("{}", symbol.to_uppercase()))
                .field("Bid", format!("{:.5}", price.bid), true)
                .field("Ask", format!("{:.5}", price.ask), true)
                .field("Spread", format!("{:.1} pips", price.spread_pips), true)
                .field("Mid", format!("{:.5}", price.mid), false)
                .color(0x1DB954)
                .timestamp(serenity::model::Timestamp::now());

            send_embed(ctx, embed).await?;
        }
        None => {
            let available = ws_client
                .get_all_prices()
                .keys()
                .take(10)
                .cloned()
                .collect::<Vec<_>>()
                .join(", ");

            let desc = if available.is_empty() {
                format!(
                    "No data for **{}**. Service may still be connecting.\n\nTry again in a few seconds.",
                    symbol.to_uppercase()
                )
            } else {
                format!(
                    "No data for **{}**.\n\nAvailable: {}",
                    symbol.to_uppercase(),
                    available.to_uppercase()
                )
            };

            send_embed(
                ctx,
                CreateEmbed::new()
                    .title("Symbol Not Found")
                    .description(desc)
                    .color(0xff0000),
            )
            .await?;
        }
    }

    Ok(())
}

#[poise::command(slash_command, prefix_command)]
pub async fn chart(
    ctx: Context<'_>,
    #[description = "Symbol (e.g., xauusd, eurusd)"] symbol: String,
    #[description = "Timeframe: 1m, 5m, 15m, 1h, 4h (default: 1h)"] timeframe: Option<String>,
    #[description = "Number of candles (10-200)"] limit: Option<u32>,
) -> Result<(), Error> {
    let api_client = match get_forex_api() {
        Some(c) => c,
        None => {
            send_embed(
                ctx,
                CreateEmbed::new()
                    .title("Error")
                    .description("Forex API not available")
                    .color(0xff0000),
            )
            .await?;
            return Ok(());
        }
    };

    let tf = timeframe.unwrap_or_else(|| "1h".to_string());
    let lim = limit.unwrap_or(50).clamp(10, 200);

    ctx.defer().await?;

    match api_client.get_chart(&symbol.to_lowercase(), &tf, lim).await {
        Ok(image_bytes) => {
            let attachment = CreateAttachment::bytes(
                image_bytes,
                format!("{}_{}.png", symbol.to_lowercase(), tf),
            );

            let embed = CreateEmbed::new()
                .title(format!("{} Chart - {}", symbol.to_uppercase(), tf))
                .image(format!("attachment://{}_{}.png", symbol.to_lowercase(), tf))
                .color(0x1DB954)
                .timestamp(serenity::model::Timestamp::now());

            ctx.send(
                poise::CreateReply::default()
                    .embed(embed)
                    .attachment(attachment),
            )
            .await?;
        }
        Err(e) => {
            send_embed(
                ctx,
                CreateEmbed::new()
                    .title("Chart Error")
                    .description(format!(
                        "Failed to generate chart for **{}**\n\n{}",
                        symbol.to_uppercase(),
                        e
                    ))
                    .color(0xff0000),
            )
            .await?;
        }
    }

    Ok(())
}

#[poise::command(slash_command, prefix_command)]
pub async fn compare(
    ctx: Context<'_>,
    #[description = "First symbol (e.g., eurusd)"] symbol1: String,
    #[description = "Second symbol (e.g., gbpusd)"] symbol2: String,
    #[description = "Third symbol (optional)"] symbol3: Option<String>,
    #[description = "Fourth symbol (optional)"] symbol4: Option<String>,
    #[description = "Time period in minutes (5-1440)"] minutes: Option<u32>,
) -> Result<(), Error> {
    let api_client = match get_forex_api() {
        Some(c) => c,
        None => {
            send_embed(
                ctx,
                CreateEmbed::new()
                    .title("Error")
                    .description("Forex API not available")
                    .color(0xff0000),
            )
            .await?;
            return Ok(());
        }
    };

    let mut symbols = vec![symbol1.as_str(), symbol2.as_str()];
    if let Some(ref s3) = symbol3 {
        symbols.push(s3.as_str());
    }
    if let Some(ref s4) = symbol4 {
        symbols.push(s4.as_str());
    }

    let mins = minutes.unwrap_or(60).clamp(5, 1440);

    ctx.defer().await?;

    match api_client.get_comparison_chart(&symbols, mins).await {
        Ok(image_bytes) => {
            let symbols_str = symbols.join("_");
            let attachment =
                CreateAttachment::bytes(image_bytes, format!("compare_{}.png", symbols_str));

            let embed = CreateEmbed::new()
                .title("Pair Comparison")
                .description(format!(
                    "Comparing: **{}**\nPeriod: {} minutes",
                    symbols
                        .iter()
                        .map(|s| s.to_uppercase())
                        .collect::<Vec<_>>()
                        .join(", "),
                    mins
                ))
                .image(format!("attachment://compare_{}.png", symbols_str))
                .color(0x1DB954)
                .timestamp(serenity::model::Timestamp::now());

            ctx.send(
                poise::CreateReply::default()
                    .embed(embed)
                    .attachment(attachment),
            )
            .await?;
        }
        Err(e) => {
            send_embed(
                ctx,
                CreateEmbed::new()
                    .title("Comparison Error")
                    .description(format!("Failed to generate comparison chart\n\n{}", e))
                    .color(0xff0000),
            )
            .await?;
        }
    }

    Ok(())
}

#[poise::command(slash_command, prefix_command)]
pub async fn analysis(
    ctx: Context<'_>,
    #[description = "Symbol (e.g., xauusd, eurusd)"] symbol: String,
    #[description = "Timeframe: 1m, 5m, 15m, 1h, 4h (default: 1h)"] timeframe: Option<String>,
) -> Result<(), Error> {
    let api_client = match get_forex_api() {
        Some(c) => c,
        None => {
            send_embed(
                ctx,
                CreateEmbed::new()
                    .title("Error")
                    .description("Forex API not available")
                    .color(0xff0000),
            )
            .await?;
            return Ok(());
        }
    };

    let tf = timeframe.unwrap_or_else(|| "1h".to_string());

    ctx.defer().await?;

    match api_client.get_indicators(&symbol.to_lowercase(), &tf).await {
        Ok(indicators) => {
            let trend_label = match indicators.trend_direction.as_str() {
                "bullish" => "[BULLISH]",
                "bearish" => "[BEARISH]",
                _ => "[NEUTRAL]",
            };

            let rsi_status = match indicators.rsi_signal.as_str() {
                "overbought" => "Overbought",
                "oversold" => "Oversold",
                _ => "Neutral",
            };

            let mut ma_text = String::new();
            if let Some(sma20) = indicators.sma_20 {
                ma_text.push_str(&format!("SMA 20: {:.5}\n", sma20));
            }
            if let Some(sma50) = indicators.sma_50 {
                ma_text.push_str(&format!("SMA 50: {:.5}\n", sma50));
            }
            if let Some(sma200) = indicators.sma_200 {
                ma_text.push_str(&format!("SMA 200: {:.5}\n", sma200));
            }

            let mut oscillator_text = String::new();
            if let Some(rsi) = indicators.rsi_14 {
                oscillator_text.push_str(&format!("RSI(14): {:.2} [{}]\n", rsi, rsi_status));
            }
            if let Some(macd) = indicators.macd {
                let signal = indicators.macd_signal.unwrap_or(0.0);
                let hist = indicators.macd_histogram.unwrap_or(0.0);
                oscillator_text.push_str(&format!(
                    "MACD: {:.5}\nSignal: {:.5}\nHist: {:.5}\n",
                    macd, signal, hist
                ));
            }

            let mut volatility_text = String::new();
            if let Some(atr) = indicators.atr_14 {
                volatility_text.push_str(&format!("ATR(14): {:.5}\n", atr));
            }
            if let Some(bb_upper) = indicators.bollinger_upper {
                let bb_middle = indicators.bollinger_middle.unwrap_or(0.0);
                let bb_lower = indicators.bollinger_lower.unwrap_or(0.0);
                volatility_text.push_str(&format!(
                    "BB Upper: {:.5}\nBB Middle: {:.5}\nBB Lower: {:.5}\n",
                    bb_upper, bb_middle, bb_lower
                ));
            }

            let embed = CreateEmbed::new()
                .title(format!(
                    "{} Analysis - {} {}",
                    symbol.to_uppercase(),
                    tf,
                    trend_label
                ))
                .field(
                    "Moving Averages",
                    if ma_text.is_empty() {
                        "N/A".to_string()
                    } else {
                        ma_text
                    },
                    true,
                )
                .field(
                    "Oscillators",
                    if oscillator_text.is_empty() {
                        "N/A".to_string()
                    } else {
                        oscillator_text
                    },
                    true,
                )
                .field(
                    "Volatility",
                    if volatility_text.is_empty() {
                        "N/A".to_string()
                    } else {
                        volatility_text
                    },
                    true,
                )
                .field(
                    "Trend",
                    format!("{}", indicators.trend_direction.to_uppercase()),
                    false,
                )
                .color(match indicators.trend_direction.as_str() {
                    "bullish" => 0x00ff00,
                    "bearish" => 0xff0000,
                    _ => 0x808080,
                })
                .footer(CreateEmbedFooter::new(format!(
                    "Timeframe: {} | Updated: {}",
                    tf, indicators.timestamp
                )));

            send_embed(ctx, embed).await?;
        }
        Err(_) => {
            send_embed(
                ctx,
                CreateEmbed::new()
                    .title("Analysis Error")
                    .description(format!(
                        "Failed to get analysis for **{}**\n\nNot enough data or symbol not found.",
                        symbol.to_uppercase()
                    ))
                    .color(0xff0000),
            )
            .await?;
        }
    }

    Ok(())
}

/// Create a price alert via Python service
#[poise::command(slash_command, prefix_command)]
pub async fn falert(
    ctx: Context<'_>,
    #[description = "Symbol (e.g., xauusd)"] symbol: String,
    #[description = "Condition: above, below, cross_up, cross_down"] condition: String,
    #[description = "Target price"] target: f64,
) -> Result<(), Error> {
    let api_client = match get_forex_api() {
        Some(c) => c,
        None => {
            send_embed(
                ctx,
                CreateEmbed::new()
                    .title("Error")
                    .description("Forex API not available")
                    .color(0xff0000),
            )
            .await?;
            return Ok(());
        }
    };

    let guild_id = ctx.guild_id().map(|g| g.get()).unwrap_or(0);
    let user_id = ctx.author().id.get();
    let channel_id = ctx.channel_id().get();

    match api_client
        .create_alert(guild_id, user_id, channel_id, &symbol, &condition, target)
        .await
    {
        Ok(alert) => {
            let ws_client = get_forex_ws();
            let current_price = ws_client
                .and_then(|c| c.get_price(&symbol.to_lowercase()))
                .map(|p| format!("{:.5}", p.mid))
                .unwrap_or_else(|| "N/A".to_string());

            let embed = CreateEmbed::new()
                .title("Alert Created")
                .description(format!(
                    "Alert **#{}** set!\n\n**{}** {} **{:.5}**\n\nCurrent: {}",
                    alert.id,
                    symbol.to_uppercase(),
                    condition,
                    target,
                    current_price
                ))
                .color(0x00ff00)
                .footer(CreateEmbedFooter::new(
                    "You'll be notified when the price is reached",
                ));

            send_embed(ctx, embed).await?;
        }
        Err(e) => {
            send_embed(
                ctx,
                CreateEmbed::new()
                    .title("Alert Error")
                    .description(format!("Failed to create alert: {}", e))
                    .color(0xff0000),
            )
            .await?;
        }
    }

    Ok(())
}

/// List your forex alerts from Python service
#[poise::command(slash_command, prefix_command)]
pub async fn falerts(ctx: Context<'_>) -> Result<(), Error> {
    let api_client = match get_forex_api() {
        Some(c) => c,
        None => {
            send_embed(
                ctx,
                CreateEmbed::new()
                    .title("Error")
                    .description("Forex API not available")
                    .color(0xff0000),
            )
            .await?;
            return Ok(());
        }
    };

    let user_id = ctx.author().id.get();

    match api_client.get_user_alerts(user_id).await {
        Ok(alerts) => {
            if alerts.is_empty() {
                send_embed(
                    ctx,
                    CreateEmbed::new()
                        .title("Your Alerts")
                        .description(
                            "No active alerts.\n\nUse `/falert <symbol> <condition> <price>` to create one.",
                        )
                        .color(0x808080),
                )
                .await?;
                return Ok(());
            }

            let mut description = String::new();
            for alert in &alerts {
                description.push_str(&format!(
                    "**#{}** {} {} {:.5}\n",
                    alert.id,
                    alert.symbol.to_uppercase(),
                    alert.condition,
                    alert.target_price
                ));
            }

            let embed = CreateEmbed::new()
                .title("Your Alerts")
                .description(description)
                .footer(CreateEmbedFooter::new("Use /falertremove <id> to remove"))
                .color(0x1DB954);

            send_embed(ctx, embed).await?;
        }
        Err(e) => {
            send_embed(
                ctx,
                CreateEmbed::new()
                    .title("Error")
                    .description(format!("Failed to get alerts: {}", e))
                    .color(0xff0000),
            )
            .await?;
        }
    }

    Ok(())
}

/// Remove a forex alert
#[poise::command(slash_command, prefix_command)]
pub async fn falertremove(
    ctx: Context<'_>,
    #[description = "Alert ID to remove"] id: i64,
) -> Result<(), Error> {
    let api_client = match get_forex_api() {
        Some(c) => c,
        None => {
            send_embed(
                ctx,
                CreateEmbed::new()
                    .title("Error")
                    .description("Forex API not available")
                    .color(0xff0000),
            )
            .await?;
            return Ok(());
        }
    };

    match api_client.delete_alert(id).await {
        Ok(_) => {
            send_embed(
                ctx,
                CreateEmbed::new()
                    .title("Alert Removed")
                    .description(format!("Alert **#{}** has been removed", id))
                    .color(0x00ff00),
            )
            .await?;
        }
        Err(e) => {
            send_embed(
                ctx,
                CreateEmbed::new()
                    .title("Error")
                    .description(format!("Failed to remove alert: {}", e))
                    .color(0xff0000),
            )
            .await?;
        }
    }

    Ok(())
}
