use crate::repository::{CalendarRepository, DbPool, ForexRepository, StockRepository};
use futures_util::{SinkExt, StreamExt};
use poise::serenity_prelude::{ChannelId, CreateEmbed, CreateMessage, Http};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use std::time::Duration;
use tokio_tungstenite::{connect_async, tungstenite::Message};

const RECONNECT_DELAY_BASE: u64 = 5;
const RECONNECT_DELAY_MAX: u64 = 300;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NewsEvent {
    pub event: String,
    pub data: Option<NewsEventData>,
    pub timestamp: Option<String>,
    pub channel: Option<String>,
    pub message: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NewsEventData {
    pub article: Option<ArticleData>,
    pub discord_embed: Option<DiscordEmbed>,
    pub alert: Option<bool>,
    pub mention_everyone: Option<bool>,
    pub calendar_event: Option<CalendarEventData>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CalendarEventData {
    pub event_id: String,
    pub title: String,
    pub country: String,
    pub currency: String,
    pub date_wib: String,
    pub impact: String,
    pub forecast: String,
    pub previous: String,
    pub minutes_until: i32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ArticleData {
    pub id: String,
    pub title: String,
    pub title_id: Option<String>,
    pub summary: Option<String>,
    pub summary_id: Option<String>, // Indonesian summary
    pub source_name: String,
    pub original_url: String,
    pub sentiment: Option<String>,
    pub sentiment_confidence: Option<f64>,
    pub impact_level: Option<String>,
    pub impact_score: Option<i32>,
    pub currency_pairs: Vec<String>,
    pub currencies: Vec<String>,
    pub published_at: Option<String>,
    pub processed_at: String,
    pub image_url: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DiscordEmbed {
    pub title: Option<String>,
    pub description: Option<String>,
    pub url: Option<String>,
    pub color: Option<u32>,
    pub fields: Option<Vec<EmbedField>>,
    pub thumbnail: Option<EmbedThumbnail>,
    pub timestamp: Option<String>,
    pub footer: Option<EmbedFooter>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EmbedField {
    pub name: String,
    pub value: String,
    #[serde(default)]
    pub inline: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EmbedThumbnail {
    pub url: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EmbedFooter {
    pub text: String,
}

pub struct NewsWebSocketService {
    db: DbPool,
    http: Arc<Http>,
    ws_url: String,
    bot_id: String,
}

impl NewsWebSocketService {
    pub fn new(db: DbPool, http: Arc<Http>, ws_url: String, bot_id: String) -> Self {
        Self {
            db,
            http,
            ws_url,
            bot_id,
        }
    }

    pub async fn start(self: Arc<Self>) {
        println!("[NEWS-WS] Starting WebSocket service...");

        let mut reconnect_delay = RECONNECT_DELAY_BASE;

        loop {
            match self.connect_and_listen().await {
                Ok(_) => {
                    println!("[NEWS-WS] Connection closed normally");
                    reconnect_delay = RECONNECT_DELAY_BASE;
                }
                Err(e) => {
                    println!("[NEWS-WS] Connection error: {}", e);
                }
            }

            println!("[NEWS-WS] Reconnecting in {} seconds...", reconnect_delay);
            tokio::time::sleep(Duration::from_secs(reconnect_delay)).await;

            reconnect_delay = (reconnect_delay * 2).min(RECONNECT_DELAY_MAX);
        }
    }

    async fn connect_and_listen(&self) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        let url = format!(
            "{}/api/v1/stream/ws/discord?bot_id={}",
            self.ws_url, self.bot_id
        );

        println!("[NEWS-WS] Connecting to: {}", url);

        let (ws_stream, _) = connect_async(&url).await?;
        let (mut write, mut read) = ws_stream.split();

        println!("[OK] News WebSocket connected!");

        let mut heartbeat_interval = tokio::time::interval(Duration::from_secs(30));

        loop {
            tokio::select! {
                _ = heartbeat_interval.tick() => {
                    let heartbeat = serde_json::json!({
                        "event": "heartbeat",
                        "data": {}
                    });
                    write.send(Message::Text(heartbeat.to_string())).await?;
                }

                msg = read.next() => {
                    match msg {
                        Some(Ok(Message::Text(text))) => {
                            if let Err(e) = self.handle_message(&text).await {
                                println!("[NEWS-WS] Error handling message: {}", e);
                            }
                        }
                        Some(Ok(Message::Close(_))) => {
                            println!("[NEWS-WS] Server closed connection");
                            break;
                        }
                        Some(Ok(Message::Ping(data))) => {
                            write.send(Message::Pong(data)).await?;
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

    async fn handle_message(
        &self,
        text: &str,
    ) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        let event: NewsEvent = serde_json::from_str(text)?;

        match event.event.as_str() {
            "news.new" | "news.high_impact" => {
                self.handle_news_event(&event).await?;
            }
            "stock.news.new" | "stock.news.high_impact" => {
                self.handle_stock_news_event(&event).await?;
            }
            "calendar.reminder" => {
                self.handle_calendar_event(&event).await?;
            }
            "sentiment.alert" => {
                println!("[NEWS-WS] Received sentiment alert");
            }
            "connected" | "subscribed" | "heartbeat" => {
                // Expected system events
            }
            _ => {
                println!("[NEWS-WS] Unknown event: {}", event.event);
            }
        }

        Ok(())
    }

    async fn handle_news_event(
        &self,
        event: &NewsEvent,
    ) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        let data = event.data.as_ref().ok_or("No data in event")?;
        let article = data.article.as_ref().ok_or("No article in event")?;
        let discord_embed = data.discord_embed.as_ref().ok_or("No embed in event")?;

        // Check if already sent
        if ForexRepository::is_news_sent(&self.db, &article.id).await? {
            return Ok(());
        }

        // Get active channels
        let channels = ForexRepository::get_active_channels(&self.db).await?;

        if channels.is_empty() {
            return Ok(());
        }

        // Build embed
        let mut embed = CreateEmbed::new();

        if let Some(title) = &discord_embed.title {
            embed = embed.title(title);
        }
        if let Some(desc) = &discord_embed.description {
            embed = embed.description(desc);
        }
        if let Some(url) = &discord_embed.url {
            embed = embed.url(url);
        }
        if let Some(color) = discord_embed.color {
            embed = embed.color(color);
        }
        if let Some(fields) = &discord_embed.fields {
            for field in fields {
                embed = embed.field(&field.name, &field.value, field.inline);
            }
        }
        if let Some(thumbnail) = &discord_embed.thumbnail {
            embed = embed.thumbnail(&thumbnail.url);
        }
        if let Some(footer) = &discord_embed.footer {
            embed = embed.footer(poise::serenity_prelude::CreateEmbedFooter::new(
                &footer.text,
            ));
        }

        let is_high_impact = event.event == "news.high_impact";
        let mention_everyone = data.mention_everyone.unwrap_or(false);

        for channel in &channels {
            let channel_id = ChannelId::new(channel.channel_id as u64);

            let mut message = CreateMessage::new().embed(embed.clone());

            if is_high_impact && mention_everyone {
                message = message.content("@everyone **HIGH IMPACT NEWS**");
            }

            if let Err(e) = channel_id.send_message(&self.http, message).await {
                println!(
                    "[NEWS-WS] Failed to send to channel {}: {}",
                    channel.channel_id, e
                );
            }
        }

        // Mark as sent
        ForexRepository::insert_news(&self.db, &article.id, &article.source_name).await?;

        println!(
            "[NEWS-WS] Sent news to {} channels: {}",
            channels.len(),
            article.title
        );

        Ok(())
    }

    async fn handle_stock_news_event(
        &self,
        event: &NewsEvent,
    ) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        let data = event.data.as_ref().ok_or("No data in event")?;
        let article = data.article.as_ref().ok_or("No article in event")?;
        let discord_embed = data.discord_embed.as_ref().ok_or("No embed in event")?;

        if StockRepository::is_stock_news_sent(&self.db, &article.id).await? {
            return Ok(());
        }

        let channels = StockRepository::get_active_channels(&self.db).await?;

        if channels.is_empty() {
            return Ok(());
        }

        let mut embed = CreateEmbed::new();

        if let Some(title) = &discord_embed.title {
            embed = embed.title(title);
        }
        if let Some(desc) = &discord_embed.description {
            embed = embed.description(desc);
        }
        if let Some(url) = &discord_embed.url {
            embed = embed.url(url);
        }
        if let Some(color) = discord_embed.color {
            embed = embed.color(color);
        }
        if let Some(fields) = &discord_embed.fields {
            for field in fields {
                embed = embed.field(&field.name, &field.value, field.inline);
            }
        }
        if let Some(thumbnail) = &discord_embed.thumbnail {
            embed = embed.thumbnail(&thumbnail.url);
        }
        if let Some(footer) = &discord_embed.footer {
            embed = embed.footer(poise::serenity_prelude::CreateEmbedFooter::new(
                &footer.text,
            ));
        }

        let is_high_impact = event.event == "stock.news.high_impact";

        for channel in &channels {
            let channel_id = ChannelId::new(channel.channel_id as u64);

            let mut message = CreateMessage::new().embed(embed.clone());

            if is_high_impact && channel.mention_everyone {
                message = message.content("@everyone **BERITA SAHAM PENTING**");
            }

            if let Err(e) = channel_id.send_message(&self.http, message).await {
                println!(
                    "[STOCK-WS] Failed to send to channel {}: {}",
                    channel.channel_id, e
                );
            }
        }

        StockRepository::insert_stock_news(&self.db, &article.id, &article.source_name).await?;

        println!(
            "[STOCK-WS] Sent stock news to {} channels: {}",
            channels.len(),
            article.title
        );

        Ok(())
    }

    async fn handle_calendar_event(
        &self,
        event: &NewsEvent,
    ) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        let data = event.data.as_ref().ok_or("No data in calendar event")?;
        let calendar_event = data
            .calendar_event
            .as_ref()
            .ok_or("No calendar_event in event data")?;

        if CalendarRepository::is_event_sent(&self.db, &calendar_event.event_id).await? {
            return Ok(());
        }

        let channels = CalendarRepository::get_active_channels(&self.db).await?;

        if channels.is_empty() {
            return Ok(());
        }

        let embed = CreateEmbed::new()
            .title("CALENDAR REMINDER")
            .description(format!(
                "**{} - {}**",
                calendar_event.currency, calendar_event.title
            ))
            .field("Waktu", &calendar_event.date_wib, true)
            .field("Forecast", &calendar_event.forecast, true)
            .field("Previous", &calendar_event.previous, true)
            .field(
                "Status",
                format!(
                    "High impact event starting in {} minutes",
                    calendar_event.minutes_until
                ),
                false,
            )
            .color(0xDC3545)
            .footer(poise::serenity_prelude::CreateEmbedFooter::new("Fio"))
            .timestamp(poise::serenity_prelude::Timestamp::now());

        for channel in &channels {
            let channel_id = ChannelId::new(channel.channel_id as u64);

            let mut message = CreateMessage::new().embed(embed.clone());

            if channel.mention_everyone {
                message = message.content("@everyone **HIGH IMPACT EVENT**");
            }

            if let Err(e) = channel_id.send_message(&self.http, message).await {
                println!(
                    "[CALENDAR-WS] Failed to send to channel {}: {}",
                    channel.channel_id, e
                );
            }
        }

        CalendarRepository::insert_event(&self.db, &calendar_event.event_id, &calendar_event.title)
            .await?;

        println!(
            "[CALENDAR-WS] Sent reminder to {} channels: {}",
            channels.len(),
            calendar_event.title
        );

        Ok(())
    }
}

pub fn start_news_ws_service(db: DbPool, http: Arc<Http>, ws_url: String, bot_id: String) {
    let service = Arc::new(NewsWebSocketService::new(db, http, ws_url, bot_id));
    tokio::spawn(async move {
        service.start().await;
    });
}
