use crate::repository::{DbPool, PriceAlert, PriceAlertRepository};
use once_cell::sync::Lazy;
use parking_lot::RwLock;
use poise::serenity_prelude::{
    CreateEmbed, CreateEmbedFooter, CreateMessage, Http, Timestamp, UserId,
};
use std::collections::HashMap;
use std::sync::Arc;

#[derive(Debug, Clone)]
pub struct CachedAlert {
    pub id: i64,
    pub user_id: i64,
    pub symbol: String,
    pub target_price: f64,
    pub direction: String,
}

impl From<PriceAlert> for CachedAlert {
    fn from(alert: PriceAlert) -> Self {
        Self {
            id: alert.id,
            user_id: alert.user_id,
            symbol: alert.symbol,
            target_price: alert.target_price,
            direction: alert.direction,
        }
    }
}

static ALERT_CACHE: Lazy<Arc<RwLock<HashMap<String, Vec<CachedAlert>>>>> =
    Lazy::new(|| Arc::new(RwLock::new(HashMap::new())));

pub async fn load_alerts_to_cache(
    db: &DbPool,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let symbols = PriceAlertRepository::get_all_active_symbols(db).await?;
    let mut cache = ALERT_CACHE.write();
    cache.clear();

    let mut total = 0;
    for symbol in &symbols {
        let alerts = PriceAlertRepository::get_active_alerts_by_symbol(db, symbol).await?;
        let cached: Vec<CachedAlert> = alerts.into_iter().map(CachedAlert::from).collect();
        total += cached.len();
        cache.insert(symbol.clone(), cached);
    }

    println!("[ALERT] Loaded {} active alerts to cache", total);
    Ok(())
}

pub fn add_to_cache(alert: &PriceAlert) {
    let cached = CachedAlert::from(alert.clone());
    let mut cache = ALERT_CACHE.write();
    cache.entry(alert.symbol.clone()).or_default().push(cached);
    println!(
        "[ALERT] Added alert #{} to cache ({})",
        alert.id, alert.symbol
    );
}

pub fn remove_from_cache(alert_id: i64) {
    let mut cache = ALERT_CACHE.write();
    for alerts in cache.values_mut() {
        if let Some(pos) = alerts.iter().position(|a| a.id == alert_id) {
            alerts.remove(pos);
            println!("[ALERT] Removed alert #{} from cache", alert_id);
            return;
        }
    }
}

pub async fn check_price(
    symbol: &str,
    price: f64,
    price_str: &str,
    asset_type: &str,
    http: &Arc<Http>,
    db: &DbPool,
) {
    let triggered: Vec<CachedAlert> = {
        let cache = ALERT_CACHE.read();
        let upper = symbol.to_uppercase();
        match cache.get(&upper) {
            Some(alerts) => alerts
                .iter()
                .filter(|a| match a.direction.as_str() {
                    "above" => price >= a.target_price,
                    "below" => price <= a.target_price,
                    _ => false,
                })
                .cloned()
                .collect(),
            None => return,
        }
    };

    if triggered.is_empty() {
        return;
    }

    // Remove triggered alerts from cache
    {
        let mut cache = ALERT_CACHE.write();
        let upper = symbol.to_uppercase();
        if let Some(alerts) = cache.get_mut(&upper) {
            let triggered_ids: Vec<i64> = triggered.iter().map(|a| a.id).collect();
            alerts.retain(|a| !triggered_ids.contains(&a.id));
        }
    }

    for alert in &triggered {
        if let Err(e) = PriceAlertRepository::trigger_alert(db, alert.id).await {
            println!(
                "[ALERT] Failed to mark alert #{} as triggered: {}",
                alert.id, e
            );
            continue;
        }

        let (color, label) = match alert.direction.as_str() {
            "above" => (0x34D399u32, "naik di atas"),
            "below" => (0xF87171u32, "turun di bawah"),
            _ => (0x60A5FAu32, "mencapai"),
        };

        let price_display = if asset_type == "crypto" {
            format!("${}", price_str)
        } else {
            price_str.to_string()
        };

        let target_display = if asset_type == "crypto" {
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
