use futures_util::{SinkExt, StreamExt};
use serde::Deserialize;
use serenity::all::{ChannelId, CreateEmbed, CreateEmbedFooter, CreateMessage, Http};
use std::sync::Arc;
use tokio_tungstenite::{connect_async, tungstenite::Message as WsMessage};

use crate::error::BotError;

#[derive(Debug, Clone, Deserialize)]
pub struct StockNewsData {
    pub id: String,
    pub title: String,
    pub summary: Option<String>,
    pub content: Option<String>,
    pub source_name: String,
    pub source_url: String,
    pub original_url: String,
    pub category: String,
    pub tickers: Vec<String>,
    pub sentiment: Option<String>,
    pub impact_level: Option<String>,
    pub published_at: Option<String>,
    pub processed_at: String,
}

#[derive(Debug, Deserialize)]
pub struct StockNewsEvent {
    pub event: String,
    pub data: StockNewsData,
}

pub struct StockNewsWsClient {
    ws_url: String,
    http: Option<Arc<Http>>,
    db_pool: Option<Arc<sqlx::PgPool>>,
}

impl StockNewsWsClient {
    pub fn new(ws_url: &str) -> Self {
        Self {
            ws_url: ws_url.to_string(),
            http: None,
            db_pool: None,
        }
    }

    pub fn with_http(mut self, http: Arc<Http>) -> Self {
        self.http = Some(http);
        self
    }

    pub fn with_db(mut self, pool: Arc<sqlx::PgPool>) -> Self {
        self.db_pool = Some(pool);
        self
    }

    pub async fn connect_and_listen(&self) -> Result<(), BotError> {
        let url = format!("{}/api/v1/stock/ws", self.ws_url.trim_end_matches('/'));
        
        loop {
            println!("[STOCK-WS] Connecting to {}", url);
            
            match connect_async(&url).await {
                Ok((ws_stream, _)) => {
                    println!("[STOCK-WS] Connected successfully");
                    
                    let (mut write, mut read) = ws_stream.split();
                    
                    let subscribe_msg = serde_json::json!({
                        "action": "subscribe",
                        "channels": ["stock.new", "stock.high_impact"]
                    });
                    
                    if let Err(e) = write.send(WsMessage::Text(subscribe_msg.to_string().into())).await {
                        eprintln!("[STOCK-WS] Failed to subscribe: {}", e);
                    }
                    
                    while let Some(msg) = read.next().await {
                        match msg {
                            Ok(WsMessage::Text(text)) => {
                                self.handle_message(&text).await;
                            }
                            Ok(WsMessage::Ping(data)) => {
                                let _ = write.send(WsMessage::Pong(data)).await;
                            }
                            Ok(WsMessage::Close(_)) => {
                                println!("[STOCK-WS] Server closed connection");
                                break;
                            }
                            Err(e) => {
                                eprintln!("[STOCK-WS] Error: {}", e);
                                break;
                            }
                            _ => {}
                        }
                    }
                }
                Err(e) => {
                    eprintln!("[STOCK-WS] Connection failed: {}", e);
                }
            }
            
            println!("[STOCK-WS] Reconnecting in 10 seconds...");
            tokio::time::sleep(tokio::time::Duration::from_secs(10)).await;
        }
    }

    async fn handle_message(&self, text: &str) {
        if let Ok(event) = serde_json::from_str::<StockNewsEvent>(text) {
            match event.event.as_str() {
                "stock.new" | "stock.high_impact" => {
                    println!("[STOCK-WS] Received stock news: {}", event.data.title);
                    if let (Some(http), Some(pool)) = (&self.http, &self.db_pool) {
                        self.broadcast_stock_news(&event.data, event.event.as_str(), http, pool).await;
                    }
                }
                _ => {}
            }
        }
    }

    async fn broadcast_stock_news(&self, data: &StockNewsData, event_type: &str, http: &Arc<Http>, pool: &Arc<sqlx::PgPool>) {
        let channels: Vec<(i64, bool)> = match sqlx::query_as(
            "SELECT channel_id, mention_everyone FROM stock_news_channels WHERE is_active = TRUE"
        )
        .fetch_all(pool.as_ref())
        .await {
            Ok(c) => c,
            Err(e) => {
                eprintln!("[STOCK-WS] Failed to get channels: {}", e);
                return;
            }
        };

        if channels.is_empty() {
            return;
        }

        // Build embed
        let embed = self.build_stock_embed(data);
        
        // Send to all channels
        for (channel_id, mention_everyone) in &channels {
            let channel = ChannelId::new(*channel_id as u64);
            
            let mut message = CreateMessage::new().embed(embed.clone());
            
            if event_type == "stock.high_impact" && *mention_everyone {
                message = message.content("@everyone **HIGH IMPACT STOCK NEWS**");
            }
            
            if let Err(e) = channel.send_message(http, message).await {
                eprintln!("[STOCK-WS] Failed to send to channel {}: {}", channel_id, e);
            }
        }
    }

    fn build_stock_embed(&self, data: &StockNewsData) -> CreateEmbed {
        // Color based on sentiment
        let color = match data.sentiment.as_deref() {
            Some("bullish") => 0x00FF00,
            Some("bearish") => 0xFF0000,
            _ => 0x2962FF,  // Default blue
        };

        // Impact bars
        let impact_bar = match data.impact_level.as_deref() {
            Some("high") => "HIGH",
            Some("medium") => "MED",
            Some("low") => "LOW",
            _ => "-",
        };

        // Category label
        let category_label = match data.category.as_str() {
            "market" => "MARKET",
            "emiten" => "EMITEN",
            "idx" => "IDX",
            "corporate" => "CORPORATE",
            _ => "SAHAM",
        };

        // Tickers display
        let tickers_str = if !data.tickers.is_empty() {
            format!(" | {}", data.tickers.iter().take(5).cloned().collect::<Vec<_>>().join(", "))
        } else {
            String::new()
        };

        // Time
        let time_str = data.published_at.as_ref()
            .and_then(|t| chrono::DateTime::parse_from_rfc3339(t).ok())
            .map(|dt| dt.format("%H:%M WIB").to_string())
            .unwrap_or_default();

        // Build embed
        let mut embed = CreateEmbed::new()
            .title(format!("{}{}", category_label, tickers_str))
            .description(&data.title)
            .color(color)
            .footer(CreateEmbedFooter::new(format!(
                "Stock Alert | {} | {}",
                data.source_name,
                time_str
            )));

        // Add summary if available
        if let Some(summary) = &data.summary {
            embed = embed.field("Ringkasan", summary, false);
        }

        // Add time and impact
        embed = embed
            .field("Waktu", if time_str.is_empty() { "N/A" } else { &time_str }, true)
            .field("Impact", impact_bar, true);

        // Add source link
        embed = embed.field("Sumber", format!("[Baca Selengkapnya]({})", data.original_url), false);

        embed
    }
}

// Global instance
use std::sync::OnceLock;
use tokio::sync::RwLock;

static STOCK_WS_CLIENT: OnceLock<RwLock<Option<Arc<StockNewsWsClient>>>> = OnceLock::new();

pub fn init_stock_ws_client(ws_url: &str, http: Arc<Http>, pool: Arc<sqlx::PgPool>) {
    let client = Arc::new(StockNewsWsClient::new(ws_url).with_http(http).with_db(pool));
    let _ = STOCK_WS_CLIENT.set(RwLock::new(Some(client)));
}

pub async fn get_stock_ws_client_async() -> Option<Arc<StockNewsWsClient>> {
    STOCK_WS_CLIENT.get()?.read().await.clone()
}
