# Discord Bot WebSocket Integration (Rust)

Contoh code untuk menghubungkan Discord bot Rust ke News Intelligence API WebSocket.

## WebSocket Endpoints

| Endpoint | Description |
|----------|-------------|
| `ws://localhost:8000/api/v1/stream/ws` | General WebSocket |
| `ws://localhost:8000/api/v1/stream/ws/discord` | Dedicated Discord bot endpoint |

## Connection URL

```
ws://localhost:8000/api/v1/stream/ws/discord?bot_id=YOUR_BOT_ID&guild_id=YOUR_GUILD_ID
```

## Event Types

| Event | Description | Channel |
|-------|-------------|---------|
| `news.new` | New article processed | `news` |
| `news.high_impact` | High impact alert | `high_impact` |
| `sentiment.alert` | Sentiment shift | `sentiment` |
| `analysis.complete` | Analysis done | `analysis` |

## Rust Example (tokio-tungstenite)

```rust
// Cargo.toml dependencies:
// tokio-tungstenite = { version = "0.21", features = ["native-tls"] }
// tokio = { version = "1", features = ["full"] }
// serde = { version = "1", features = ["derive"] }
// serde_json = "1"
// futures-util = "0.3"

use futures_util::{SinkExt, StreamExt};
use serde::{Deserialize, Serialize};
use tokio_tungstenite::{connect_async, tungstenite::Message};

#[derive(Debug, Deserialize)]
struct WebSocketMessage {
    event: String,
    data: serde_json::Value,
    timestamp: Option<String>,
    channel: Option<String>,
}

#[derive(Debug, Deserialize)]
struct NewsArticle {
    id: String,
    title: String,
    title_id: Option<String>,
    summary: Option<String>,
    source_name: String,
    original_url: String,
    sentiment: Option<String>,
    sentiment_confidence: Option<f64>,
    impact_level: Option<String>,
    currency_pairs: Vec<String>,
}

#[derive(Debug, Deserialize)]
struct NewsEventData {
    article: NewsArticle,
    discord_embed: serde_json::Value,
}

#[derive(Debug, Serialize)]
struct SubscribeMessage {
    event: String,
    data: SubscribeData,
}

#[derive(Debug, Serialize)]
struct SubscribeData {
    channels: Vec<String>,
}

pub struct NewsWebSocket {
    bot_id: String,
    guild_id: Option<String>,
    api_url: String,
}

impl NewsWebSocket {
    pub fn new(bot_id: &str, guild_id: Option<&str>, api_url: &str) -> Self {
        Self {
            bot_id: bot_id.to_string(),
            guild_id: guild_id.map(String::from),
            api_url: api_url.to_string(),
        }
    }

    pub async fn connect<F>(&self, on_message: F) -> Result<(), Box<dyn std::error::Error>>
    where
        F: Fn(WebSocketMessage) + Send + 'static,
    {
        let url = format!(
            "{}/api/v1/stream/ws/discord?bot_id={}{}",
            self.api_url.replace("http", "ws"),
            self.bot_id,
            self.guild_id
                .as_ref()
                .map(|g| format!("&guild_id={}", g))
                .unwrap_or_default()
        );

        println!("Connecting to WebSocket: {}", url);

        let (ws_stream, _) = connect_async(&url).await?;
        let (mut write, mut read) = ws_stream.split();

        println!("Connected to News Intelligence WebSocket!");

        // Handle incoming messages
        while let Some(msg) = read.next().await {
            match msg {
                Ok(Message::Text(text)) => {
                    if let Ok(ws_msg) = serde_json::from_str::<WebSocketMessage>(&text) {
                        on_message(ws_msg);
                    }
                }
                Ok(Message::Ping(data)) => {
                    let _ = write.send(Message::Pong(data)).await;
                }
                Ok(Message::Close(_)) => {
                    println!("WebSocket closed");
                    break;
                }
                Err(e) => {
                    eprintln!("WebSocket error: {}", e);
                    break;
                }
                _ => {}
            }
        }

        Ok(())
    }
}

// Example usage with Serenity Discord bot
#[tokio::main]
async fn main() {
    let news_ws = NewsWebSocket::new(
        "my-discord-bot",
        Some("123456789"),
        "http://localhost:8000",
    );

    // Connect and handle messages
    let _ = news_ws.connect(|msg| {
        match msg.event.as_str() {
            "news.new" => {
                println!("📰 New article received!");
                if let Ok(data) = serde_json::from_value::<NewsEventData>(msg.data) {
                    println!("Title: {}", data.article.title);
                    if let Some(title_id) = &data.article.title_id {
                        println!("Title (ID): {}", title_id);
                    }
                    if let Some(sentiment) = &data.article.sentiment {
                        println!("Sentiment: {}", sentiment);
                    }
                    // Send to Discord channel using discord_embed
                    // ctx.http.send_message(channel_id, |m| m.embed(|e| ...))
                }
            }
            "news.high_impact" => {
                println!("🚨 HIGH IMPACT ALERT!");
                // Handle high impact - maybe @everyone
            }
            "sentiment.alert" => {
                println!("📊 Sentiment Alert!");
            }
            "connected" => {
                println!("✅ Connected to server");
            }
            _ => {
                println!("Unknown event: {}", msg.event);
            }
        }
    }).await;
}
```

## Serenity Integration

```rust
use serenity::prelude::*;
use serenity::model::channel::Message;
use serenity::builder::CreateEmbed;
use tokio::sync::mpsc;

struct Handler {
    news_receiver: mpsc::Receiver<NewsEventData>,
}

#[async_trait]
impl EventHandler for Handler {
    async fn ready(&self, ctx: Context, ready: Ready) {
        println!("{} is connected!", ready.user.name);
        
        // Start news listener
        let ctx_clone = ctx.clone();
        tokio::spawn(async move {
            listen_for_news(ctx_clone).await;
        });
    }
}

async fn listen_for_news(ctx: Context) {
    let news_ws = NewsWebSocket::new("discord-bot", None, "http://localhost:8000");
    
    let channel_id = ChannelId(YOUR_CHANNEL_ID);
    
    let _ = news_ws.connect(move |msg| {
        let ctx = ctx.clone();
        
        tokio::spawn(async move {
            if msg.event == "news.new" {
                if let Ok(data) = serde_json::from_value::<NewsEventData>(msg.data) {
                    // Create embed from server-provided data
                    let embed = create_embed_from_data(&data);
                    
                    let _ = channel_id.send_message(&ctx.http, |m| {
                        m.embed(|e| {
                            *e = embed;
                            e
                        })
                    }).await;
                }
            } else if msg.event == "news.high_impact" {
                // Send with @everyone for high impact
                let _ = channel_id.send_message(&ctx.http, |m| {
                    m.content("@everyone 🚨 **HIGH IMPACT NEWS**")
                }).await;
            }
        });
    }).await;
}

fn create_embed_from_data(data: &NewsEventData) -> CreateEmbed {
    let mut embed = CreateEmbed::default();
    
    embed.title(data.article.title_id.as_ref().unwrap_or(&data.article.title));
    embed.url(&data.article.original_url);
    embed.description(format!("Source: {}", data.article.source_name));
    
    // Color based on sentiment
    let color = match data.article.sentiment.as_deref() {
        Some("bullish") => 0x00FF00,
        Some("bearish") => 0xFF0000,
        _ => 0x808080,
    };
    embed.color(color);
    
    // Add fields
    if let Some(sentiment) = &data.article.sentiment {
        let conf = data.article.sentiment_confidence.unwrap_or(0.0);
        embed.field("📊 Sentiment", format!("{} ({:.0}%)", sentiment.to_uppercase(), conf * 100.0), true);
    }
    
    if let Some(impact) = &data.article.impact_level {
        let emoji = match impact.as_str() {
            "high" => "🔴",
            "medium" => "🟡",
            _ => "🟢",
        };
        embed.field("💥 Impact", format!("{} {}", emoji, impact.to_uppercase()), true);
    }
    
    if !data.article.currency_pairs.is_empty() {
        embed.field("💱 Pairs", data.article.currency_pairs.join(", "), true);
    }
    
    if let Some(summary) = &data.article.summary {
        embed.field("📝 Summary", summary, false);
    }
    
    embed
}
```

## Testing

Test WebSocket dengan curl atau wscat:

```bash
# Install wscat
npm install -g wscat

# Connect
wscat -c "ws://localhost:8000/api/v1/stream/ws/discord?bot_id=test-bot"

# Send test news via API
curl -X POST http://localhost:8000/api/v1/stream/ws/test-news

# Send high impact test
curl -X POST http://localhost:8000/api/v1/stream/ws/test-high-impact
```

## Message Format

### News Event
```json
{
    "event": "news.new",
    "data": {
        "article": {
            "id": "abc123",
            "title": "Fed Raises Interest Rates",
            "title_id": "Fed Menaikkan Suku Bunga",
            "summary": "The Federal Reserve...",
            "source_name": "Reuters",
            "original_url": "https://...",
            "sentiment": "bearish",
            "sentiment_confidence": 0.85,
            "impact_level": "high",
            "currency_pairs": ["EUR/USD", "USD/JPY"],
            "currencies": ["USD", "EUR"]
        },
        "discord_embed": {
            "title": "Fed Menaikkan Suku Bunga",
            "color": 16711680,
            "fields": [...]
        }
    },
    "timestamp": "2026-02-01T10:30:00Z",
    "channel": "news"
}
```

### High Impact Alert
```json
{
    "event": "news.high_impact",
    "data": {
        "article": {...},
        "discord_embed": {...},
        "alert": true,
        "mention_everyone": true
    }
}
```
