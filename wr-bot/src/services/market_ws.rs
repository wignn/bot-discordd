use once_cell::sync::Lazy;
use parking_lot::RwLock;
use serde::Deserialize;
use std::collections::HashMap;
use std::sync::Arc;

#[derive(Debug, Clone, Deserialize)]
pub struct MarketTradeEvent {
    pub event: String,
    pub data: Option<MarketTradeData>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct MarketTradeData {
    pub symbol: String,
    pub price: f64,
    pub price_str: String,
    pub direction: String,
    pub asset_type: String,
    pub volume_str: Option<String>,
    pub trade_time: Option<String>,
}

#[derive(Debug, Clone)]
pub struct CachedPrice {
    pub symbol: String,
    pub price: f64,
    pub price_str: String,
    pub direction: String,
    pub asset_type: String,
    pub updated_at: std::time::Instant,
}

static PRICE_CACHE: Lazy<Arc<RwLock<HashMap<String, CachedPrice>>>> =
    Lazy::new(|| Arc::new(RwLock::new(HashMap::new())));

pub fn update_price(data: &MarketTradeData) {
    let mut cache = PRICE_CACHE.write();
    cache.insert(
        data.symbol.clone(),
        CachedPrice {
            symbol: data.symbol.clone(),
            price: data.price,
            price_str: data.price_str.clone(),
            direction: data.direction.clone(),
            asset_type: data.asset_type.clone(),
            updated_at: std::time::Instant::now(),
        },
    );
}

pub fn get_price(symbol: &str) -> Option<CachedPrice> {
    let cache = PRICE_CACHE.read();
    let upper = symbol.to_uppercase();
    cache.get(&upper).cloned()
}

pub fn get_all_prices() -> Vec<CachedPrice> {
    let cache = PRICE_CACHE.read();
    cache.values().cloned().collect()
}

pub fn get_xauusd_display() -> Option<String> {
    get_price("XAUUSD").map(|p| {
        format!("XAUUSD ${:.2}", p.price)
    })
}
