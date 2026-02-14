use crate::repository::{DbPool, PriceAlertRepository};
use crate::services::market_ws;
use poise::serenity_prelude::{
    CreateEmbed, CreateEmbedFooter, CreateMessage, Http, Timestamp, UserId,
};
use std::sync::Arc;
use std::time::Duration;

const CHECK_INTERVAL_SECS: u64 = 5;

pub fn start_price_alert_checker(db: DbPool, http: Arc<Http>) {
    tokio::spawn(async move {
        println!("[ALERT] Price alert checker started");

        let mut interval = tokio::time::interval(Duration::from_secs(CHECK_INTERVAL_SECS));

        loop {
            interval.tick().await;

            if let Err(e) = check_alerts(&db, &http).await {
                println!("[ALERT] Error checking alerts: {}", e);
            }
        }
    });
}

async fn check_alerts(
    db: &DbPool,
    http: &Arc<Http>,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let symbols = PriceAlertRepository::get_all_active_symbols(db).await?;

    if symbols.is_empty() {
        return Ok(());
    }

    for symbol in &symbols {
        let current = match market_ws::get_price(symbol) {
            Some(cached) => cached,
            None => continue,
        };

        let alerts = PriceAlertRepository::get_active_alerts_by_symbol(db, symbol).await?;

        for alert in &alerts {
            let triggered = match alert.direction.as_str() {
                "above" => current.price >= alert.target_price,
                "below" => current.price <= alert.target_price,
                _ => false,
            };

            if triggered {
                PriceAlertRepository::trigger_alert(db, alert.id).await?;

                let (color, label) = match alert.direction.as_str() {
                    "above" => (0x34D399u32, "naik di atas"),
                    "below" => (0xF87171u32, "turun di bawah"),
                    _ => (0x60A5FAu32, "mencapai"),
                };

                let price_display = if current.asset_type == "crypto" {
                    format!("${}", current.price_str)
                } else {
                    current.price_str.clone()
                };

                let target_display = if current.asset_type == "crypto" {
                    format!("${:.2}", alert.target_price)
                } else {
                    format!("{:.5}", alert.target_price)
                };

                let embed = CreateEmbed::new()
                    .title(format!("PRICE ALERT -- {}", alert.symbol))
                    .description(format!(
                        "**{}** sudah {} target **{}**!\n\nHarga sekarang: **{}**",
                        alert.symbol, label, target_display, price_display
                    ))
                    .field("Symbol", &alert.symbol, true)
                    .field("Target", &target_display, true)
                    .field("Harga Saat Ini", &price_display, true)
                    .color(color)
                    .footer(CreateEmbedFooter::new("Fio Price Alert"))
                    .timestamp(Timestamp::now());

                let user_id = UserId::new(alert.user_id as u64);
                match user_id.create_dm_channel(http).await {
                    Ok(dm_channel) => {
                        let message = CreateMessage::new().embed(embed);
                        if let Err(e) = dm_channel.send_message(http, message).await {
                            println!("[ALERT] Failed to DM user {}: {}", alert.user_id, e);
                        } else {
                            println!(
                                "[ALERT] Triggered: {} {} {} (user {})",
                                alert.symbol, alert.direction, alert.target_price, alert.user_id
                            );
                        }
                    }
                    Err(e) => {
                        println!(
                            "[ALERT] Failed to create DM channel for user {}: {}",
                            alert.user_id, e
                        );
                    }
                }
            }
        }
    }

    Ok(())
}
