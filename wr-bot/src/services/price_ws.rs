use crate::repository::DbPool;
use crate::services::{market_ws, price_alert};
use futures_util::{SinkExt, StreamExt};
use poise::serenity_prelude::Http;
use std::sync::Arc;
use std::time::Duration;
use tokio_tungstenite::{connect_async, tungstenite::Message};

const RECONNECT_DELAY_BASE: u64 = 5;
const RECONNECT_DELAY_MAX: u64 = 300;

pub struct PriceWebSocketService {
    db: DbPool,
    http: Arc<Http>,
    ws_url: String,
}

impl PriceWebSocketService {
    pub fn new(db: DbPool, http: Arc<Http>, ws_url: String) -> Self {
        Self { db, http, ws_url }
    }

    pub async fn start(self: Arc<Self>) {
        println!("[PRICE-WS] Starting WebSocket service...");

        let mut reconnect_delay = RECONNECT_DELAY_BASE;

        loop {
            match self.connect_and_listen().await {
                Ok(_) => {
                    println!("[PRICE-WS] Connection closed normally");
                    reconnect_delay = RECONNECT_DELAY_BASE;
                }
                Err(e) => {
                    println!("[PRICE-WS] Connection error: {}", e);
                }
            }

            println!("[PRICE-WS] Reconnecting in {} seconds...", reconnect_delay);
            tokio::time::sleep(Duration::from_secs(reconnect_delay)).await;
            reconnect_delay = (reconnect_delay * 2).min(RECONNECT_DELAY_MAX);
        }
    }

    async fn connect_and_listen(&self) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        let url = self.ws_url.clone();
        println!("[PRICE-WS] Connecting to: {}", url);

        let (ws_stream, _) = connect_async(&url).await?;
        let (mut write, mut read) = ws_stream.split();

        println!("[OK] Price WebSocket connected!");

        let mut heartbeat_interval = tokio::time::interval(Duration::from_secs(30));

        loop {
            tokio::select! {
                _ = heartbeat_interval.tick() => {
                    let _ = write.send(Message::Ping(Vec::new())).await;
                }
                msg = read.next() => {
                    match msg {
                        Some(Ok(Message::Text(text))) => {
                            if let Ok(event) = serde_json::from_str::<market_ws::MarketTradeEvent>(&text) {
                                if event.event == "market.trade" {
                                    if let Some(data) = event.data {
                                        market_ws::update_price(&data);
                                        price_alert::check_price(
                                            &data.symbol,
                                            data.price,
                                            &data.price_str,
                                            &data.asset_type,
                                            &self.http,
                                            &self.db,
                                        ).await;
                                    }
                                }
                            }
                        }
                        Some(Ok(Message::Close(_))) => {
                            println!("[PRICE-WS] Server closed connection");
                            break;
                        }
                        Some(Ok(Message::Ping(data))) => {
                            let _ = write.send(Message::Pong(data)).await;
                        }
                        Some(Err(e)) => {
                            return Err(Box::new(e));
                        }
                        None => {
                            break;
                        }
                        _ => {}
                    }
                }
            }
        }

        Ok(())
    }
}

pub fn start_price_ws_service(db: DbPool, http: Arc<Http>, ws_url: String) {
    let service = Arc::new(PriceWebSocketService::new(db, http, ws_url));
    tokio::spawn(async move {
        service.start().await;
    });
}
