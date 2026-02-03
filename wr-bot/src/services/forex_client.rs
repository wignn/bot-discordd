use futures_util::{SinkExt, StreamExt};
use serde::{Deserialize, Serialize};
use serenity::all::{ChannelId, CreateEmbed, CreateMessage, Http};
use std::collections::HashMap;
use std::sync::Arc;
use parking_lot::RwLock;
use tokio::sync::mpsc;
use tokio_tungstenite::{connect_async, tungstenite::Message as WsMessage};

/// Forex price from the Python service
#[derive(Debug, Clone, Deserialize)]
pub struct ForexPrice {
    pub symbol: String,
    pub bid: f64,
    pub ask: f64,
    pub mid: f64,
    pub spread_pips: f64,
    pub timestamp: String,
}

/// Alert triggered notification from Python service
#[derive(Debug, Clone, Deserialize)]
pub struct AlertTriggered {
    pub alert_id: i64,
    pub guild_id: u64,
    pub user_id: u64,
    pub channel_id: u64,
    pub symbol: String,
    pub condition: String,
    pub target_price: f64,
    pub triggered_price: f64,
    pub triggered_at: String,
}

/// WebSocket message from server
#[derive(Debug, Deserialize)]
#[serde(tag = "type")]
pub enum ServerMessage {
    #[serde(rename = "snapshot")]
    Snapshot { data: HashMap<String, ForexPrice> },
    
    #[serde(rename = "price")]
    Price { data: ForexPrice },
    
    #[serde(rename = "subscribed")]
    Subscribed { symbols: serde_json::Value },
    
    #[serde(rename = "pong")]
    Pong,
    
    #[serde(rename = "alert_triggered")]
    AlertTriggered { data: AlertTriggered },
    
    #[serde(rename = "chart")]
    Chart { 
        symbol: String,
        timeframe: String,
        image_base64: String,
    },
    
    #[serde(rename = "error")]
    Error { message: String },
}

/// Client messages to send to server
#[derive(Debug, Serialize)]
#[serde(tag = "type")]
pub enum ClientMessage {
    #[serde(rename = "subscribe_all")]
    SubscribeAll,
    
    #[serde(rename = "subscribe")]
    Subscribe { symbols: Vec<String> },
    
    #[serde(rename = "ping")]
    Ping,
    
    #[serde(rename = "get_price")]
    GetPrice { symbol: String },
}

/// Forex WebSocket client that connects to Python service
pub struct ForexWsClient {
    url: String,
    prices: Arc<RwLock<HashMap<String, ForexPrice>>>,
    http: Option<Arc<Http>>,
}

impl ForexWsClient {
    pub fn new(service_url: &str) -> Self {
        let ws_url = format!("{}/ws/forex?client_type=bot", service_url.replace("http", "ws"));
        
        Self {
            url: ws_url,
            prices: Arc::new(RwLock::new(HashMap::new())),
            http: None,
        }
    }
    
    pub fn with_http(mut self, http: Arc<Http>) -> Self {
        self.http = Some(http);
        self
    }
    
    /// Get current price for a symbol
    pub fn get_price(&self, symbol: &str) -> Option<ForexPrice> {
        self.prices.read().get(&symbol.to_lowercase()).cloned()
    }
    
    /// Get all prices
    pub fn get_all_prices(&self) -> HashMap<String, ForexPrice> {
        self.prices.read().clone()
    }
    
    /// Start the WebSocket connection
    pub async fn start(self: Arc<Self>) {
        loop {
            println!("[FOREX-WS] Connecting to Python service at {}...", self.url);
            
            match self.connect_and_run().await {
                Ok(_) => println!("[FOREX-WS] Connection closed"),
                Err(e) => eprintln!("[FOREX-WS] Connection error: {}", e),
            }
            
            println!("[FOREX-WS] Reconnecting in 5 seconds...");
            tokio::time::sleep(tokio::time::Duration::from_secs(5)).await;
        }
    }
    
    async fn connect_and_run(&self) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        let (ws_stream, _) = connect_async(&self.url).await?;
        println!("[FOREX-WS] Connected to Python forex service");
        
        let (mut write, mut read) = ws_stream.split();
        
        // Subscribe to all symbols
        let subscribe_msg = ClientMessage::SubscribeAll;
        let msg_json = serde_json::to_string(&subscribe_msg)?;
        write.send(WsMessage::Text(msg_json)).await?;
        
        // Setup ping interval
        let (ping_tx, mut ping_rx) = mpsc::channel::<()>(1);
        tokio::spawn(async move {
            loop {
                tokio::time::sleep(tokio::time::Duration::from_secs(30)).await;
                if ping_tx.send(()).await.is_err() {
                    break;
                }
            }
        });
        
        loop {
            tokio::select! {
                msg = read.next() => {
                    match msg {
                        Some(Ok(WsMessage::Text(text))) => {
                            self.handle_message(&text).await;
                        }
                        Some(Ok(WsMessage::Close(_))) => {
                            println!("[FOREX-WS] Server closed connection");
                            break;
                        }
                        Some(Err(e)) => {
                            eprintln!("[FOREX-WS] Error: {}", e);
                            break;
                        }
                        None => break,
                        _ => {}
                    }
                }
                _ = ping_rx.recv() => {
                    let ping = ClientMessage::Ping;
                    let msg_json = serde_json::to_string(&ping)?;
                    write.send(WsMessage::Text(msg_json)).await?;
                }
            }
        }
        
        Ok(())
    }
    
    async fn handle_message(&self, text: &str) {
        let msg: ServerMessage = match serde_json::from_str(text) {
            Ok(m) => m,
            Err(e) => {
                eprintln!("[FOREX-WS] Parse error: {} - {}", e, &text[..text.len().min(100)]);
                return;
            }
        };
        
        match msg {
            ServerMessage::Snapshot { data } => {
                println!("[FOREX-WS] Received snapshot with {} prices", data.len());
                let mut prices = self.prices.write();
                for (symbol, price) in data {
                    prices.insert(symbol.to_lowercase(), price);
                }
            }
            
            ServerMessage::Price { data } => {
                self.prices.write().insert(data.symbol.to_lowercase(), data);
            }
            
            ServerMessage::Subscribed { symbols } => {
                println!("[FOREX-WS] Subscribed to: {:?}", symbols);
            }
            
            ServerMessage::Pong => {
                // Heartbeat response, ignore
            }
            
            ServerMessage::AlertTriggered { data } => {
                println!("[FOREX-WS] Alert triggered: {:?}", data);
                if let Some(http) = &self.http {
                    self.send_alert_notification(&data, http).await;
                }
            }
            
            ServerMessage::Chart { symbol, timeframe, image_base64: _ } => {
                println!("[FOREX-WS] Received chart for {} {}", symbol, timeframe);
                // Chart handling would be done via command response, not broadcast
            }
            
            ServerMessage::Error { message } => {
                eprintln!("[FOREX-WS] Server error: {}", message);
            }
        }
    }
    
    async fn send_alert_notification(&self, alert: &AlertTriggered, http: &Arc<Http>) {
        let embed = CreateEmbed::new()
            .title("Price Alert Triggered!")
            .description(format!(
                "**{}** is now {} **{:.5}**\n\n\
                Target: {:.5}\n\
                Current: {:.5}",
                alert.symbol.to_uppercase(),
                alert.condition,
                alert.target_price,
                alert.target_price,
                alert.triggered_price
            ))
            .color(0x00ff00)
            .timestamp(serenity::model::Timestamp::now());

        let channel_id = ChannelId::new(alert.channel_id);
        let message = CreateMessage::new()
            .content(format!("<@{}>", alert.user_id))
            .embed(embed);

        if let Err(e) = channel_id.send_message(http, message).await {
            eprintln!("[FOREX-WS] Failed to send alert notification: {}", e);
        }
    }
}

// HTTP client for REST API calls (charts, etc.)
pub struct ForexApiClient {
    base_url: String,
    client: reqwest::Client,
}

impl ForexApiClient {
    pub fn new(base_url: &str) -> Self {
        Self {
            base_url: base_url.trim_end_matches('/').to_string(),
            client: reqwest::Client::new(),
        }
    }
    
    /// Get chart image as bytes
    pub async fn get_chart(
        &self,
        symbol: &str,
        timeframe: &str,
        limit: u32,
    ) -> Result<Vec<u8>, reqwest::Error> {
        let url = format!(
            "{}/api/v1/forex/chart/{}?timeframe={}&limit={}",
            self.base_url, symbol, timeframe, limit
        );
        
        let response = self.client.get(&url).send().await?;
        let bytes = response.bytes().await?;
        Ok(bytes.to_vec())
    }
    
    /// Get comparison chart
    pub async fn get_comparison_chart(
        &self,
        symbols: &[&str],
        minutes: u32,
    ) -> Result<Vec<u8>, reqwest::Error> {
        let symbols_str = symbols.join(",");
        let url = format!(
            "{}/api/v1/forex/chart/compare?symbols={}&minutes={}",
            self.base_url, symbols_str, minutes
        );
        
        let response = self.client.get(&url).send().await?;
        let bytes = response.bytes().await?;
        Ok(bytes.to_vec())
    }
    
    /// Get technical indicators
    pub async fn get_indicators(
        &self,
        symbol: &str,
        timeframe: &str,
    ) -> Result<TechnicalIndicators, reqwest::Error> {
        let url = format!(
            "{}/api/v1/forex/indicators/{}?timeframe={}",
            self.base_url, symbol, timeframe
        );
        
        let response = self.client.get(&url).send().await?;
        let indicators: TechnicalIndicators = response.json().await?;
        Ok(indicators)
    }
    
    /// Create a price alert
    pub async fn create_alert(
        &self,
        guild_id: u64,
        user_id: u64,
        channel_id: u64,
        symbol: &str,
        condition: &str,
        target_price: f64,
    ) -> Result<AlertResponse, reqwest::Error> {
        let url = format!("{}/api/v1/forex/alerts", self.base_url);
        
        let body = serde_json::json!({
            "guild_id": guild_id,
            "user_id": user_id,
            "channel_id": channel_id,
            "symbol": symbol,
            "condition": condition,
            "target_price": target_price,
        });
        
        let response = self.client.post(&url).json(&body).send().await?;
        let alert: AlertResponse = response.json().await?;
        Ok(alert)
    }
    
    /// Delete an alert
    pub async fn delete_alert(&self, alert_id: i64) -> Result<(), reqwest::Error> {
        let url = format!("{}/api/v1/forex/alerts/{}", self.base_url, alert_id);
        self.client.delete(&url).send().await?;
        Ok(())
    }
    
    /// Get user's alerts
    pub async fn get_user_alerts(&self, user_id: u64) -> Result<Vec<AlertResponse>, reqwest::Error> {
        let url = format!("{}/api/v1/forex/alerts/user/{}", self.base_url, user_id);
        let response = self.client.get(&url).send().await?;
        let alerts: Vec<AlertResponse> = response.json().await?;
        Ok(alerts)
    }
}

#[derive(Debug, Deserialize)]
pub struct TechnicalIndicators {
    pub symbol: String,
    pub timestamp: String,
    pub sma_20: Option<f64>,
    pub sma_50: Option<f64>,
    pub sma_200: Option<f64>,
    pub ema_12: Option<f64>,
    pub ema_26: Option<f64>,
    pub rsi_14: Option<f64>,
    pub macd: Option<f64>,
    pub macd_signal: Option<f64>,
    pub macd_histogram: Option<f64>,
    pub atr_14: Option<f64>,
    pub bollinger_upper: Option<f64>,
    pub bollinger_middle: Option<f64>,
    pub bollinger_lower: Option<f64>,
    pub adx: Option<f64>,
    pub trend_direction: String,
    pub rsi_signal: String,
}

#[derive(Debug, Deserialize)]
pub struct AlertResponse {
    pub id: i64,
    pub guild_id: u64,
    pub user_id: u64,
    pub channel_id: u64,
    pub symbol: String,
    pub condition: String,
    pub target_price: f64,
    pub created_at: String,
    pub is_active: bool,
}

// Global instance management
use once_cell::sync::OnceCell;

static FOREX_WS_CLIENT: OnceCell<Arc<ForexWsClient>> = OnceCell::new();
static FOREX_API_CLIENT: OnceCell<ForexApiClient> = OnceCell::new();

pub fn init_forex_clients(service_url: &str, http: Arc<Http>) {
    let ws_client = Arc::new(ForexWsClient::new(service_url).with_http(http));
    let _ = FOREX_WS_CLIENT.set(ws_client);
    
    let api_client = ForexApiClient::new(service_url);
    let _ = FOREX_API_CLIENT.set(api_client);
}

pub fn get_forex_ws() -> Option<&'static Arc<ForexWsClient>> {
    FOREX_WS_CLIENT.get()
}

pub fn get_forex_api() -> Option<&'static ForexApiClient> {
    FOREX_API_CLIENT.get()
}

/// Start the forex WebSocket client
pub async fn start_forex_ws() {
    if let Some(client) = get_forex_ws() {
        client.clone().start().await;
    }
}
