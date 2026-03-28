use dotenvy::dotenv;
use poise::serenity_prelude::UserId;
use serenity::all::{ActivityData, GatewayIntents, OnlineStatus};
use std::collections::HashSet;
use std::env;
use worm::commands::{
    Data, admin, calendar, forex, general, market, moderation, ping, stock, sys,
    twitter, volatility,
};
use worm::config::Config;
use worm::error::BotError;
use worm::handlers::{handle_event, on_error};
use worm::repository::create_pool;
use worm::services::news_ws::start_news_ws_service;
use worm::services::price_ws::start_price_ws_service;

#[tokio::main]
async fn main() -> Result<(), BotError> {
    dotenv().ok();

    println!("Starting Bot...");

    let config = Config::from_env()
        .map_err(|e| BotError::Config(format!("Failed to load config: {}", e)))?;

    let intents = GatewayIntents::GUILD_MESSAGES
        | GatewayIntents::MESSAGE_CONTENT
        | GatewayIntents::GUILDS
        | GatewayIntents::GUILD_VOICE_STATES
        | GatewayIntents::GUILD_MEMBERS;

    let owner_id = env::var("CLIENT_ID")
        .unwrap_or_else(|_| "0".to_string())
        .parse::<u64>()
        .expect("CLIENT_ID must be a valid u64");

    let mut owners = HashSet::new();
    owners.insert(UserId::new(owner_id));

    let database_url = env::var("DATABASE_URL")
        .unwrap_or_else(|_| "postgres://postgres:postgres@localhost:5432/wrbot".to_string());

    let db = create_pool(&database_url)
        .await
        .map_err(|e| BotError::Config(format!("Failed to initialize database: {}", e)))?;

    println!("[OK] Database initialized successfully");

    if let Err(e) = worm::services::price_alert::load_alerts_to_cache(&db).await {
        println!("[WARN] Failed to load price alerts to cache: {}", e);
    }

    if config.is_openrouter_enabled() {
        println!("[OK] OpenRouter AI enabled (worm command)");
    } else {
        println!("[WARN] OpenRouter AI disabled (no API_KEY configured)");
    }

    if config.is_gemini_enabled() {
        println!("[OK] Gemini AI enabled");
    } else {
        println!("[WARN] Gemini AI disabled (no GEMINI_API_KEY configured)");
    }

    let owners_clone = owners.clone();
    let db_for_checker = db.clone();
    let db_for_setup = db.clone();

    let framework = poise::Framework::builder()
        .options(poise::FrameworkOptions {
            commands: vec![
                // General commands
                ping::ping(),
                general::ping(),
                general::say(),
                general::purge(),
                // Admin commands
                admin::everyone(),
                sys::sys(),
                moderation::warn(),
                moderation::warnings(),
                moderation::clearwarnings(),
                moderation::mute(),
                moderation::unmute(),
                moderation::kick(),
                moderation::ban(),
                moderation::unban(),
                // Auto-role commands
                moderation::autorole_set(),
                moderation::autorole_disable(),
                // Logging commands
                moderation::log_setup(),
                moderation::log_disable(),
                // Forex commands
                forex::forex_setup(),
                forex::forex_disable(),
                forex::forex_enable(),
                forex::forex_status(),
                forex::forex_calendar(),
                // Calendar reminder commands
                calendar::calendar_setup(),
                calendar::calendar_disable(),
                calendar::calendar_enable(),
                calendar::calendar_status(),
                calendar::calendar_mention(),
                // Stock news commands
                stock::stocknews(),
                stock::search(),
                stock::market(),
                mean::mean(),
                // Market price commands
                market::price(),
                market::prices(),
                // Price alert commands
                market::alert(),
                market::alerts(),
                market::alert_remove(),
                // Volatility spike detector commands
                volatility::volatility_setup(),
                volatility::volatility_disable(),
                volatility::volatility_status(),
                // X/Twitter feed commands
                twitter::twitter_setup(),
                twitter::twitter_disable(),
                twitter::twitter_enable(),
                twitter::twitter_status(),
            ],
            prefix_options: poise::PrefixFrameworkOptions {
                prefix: Some("!".into()),
                ..Default::default()
            },
            on_error: |error| Box::pin(on_error(error)),
            event_handler: |ctx, event, _framework, data| Box::pin(handle_event(ctx, event, data)),
            ..Default::default()
        })
        .setup(move |ctx, ready, framework| {
            let inner_db = db_for_setup.clone();
            let owners_inner = owners_clone.clone();
            Box::pin(async move {
                println!("[OK] Logged in as {}", ready.user.name);

                poise::builtins::register_globally(ctx, &framework.options().commands).await?;
                println!("[OK] Slash commands registered globally");

                Ok(Data {
                    owners: owners_inner,
                    db: inner_db,
                })
            })
        })
        .build();

    let mut client = serenity::Client::builder(&config.token, intents)
        .framework(framework)
        .await
        .map_err(|e| BotError::Client(format!("Failed to create client: {}", e)))?;

    let shard_manager = client.shard_manager.clone();
    let http = client.http.clone();
    // let cache = client.cache.clone();

    tokio::spawn(async move {
        let mut interval = tokio::time::interval(std::time::Duration::from_secs(60));
        let mut idx = 0;
        loop {
            interval.tick().await;

            // let total_users: u64 = cache
            //     .guilds()
            //     .iter()
            //     .filter_map(|guild_id| cache.guild(*guild_id))
            //     .map(|g| g.member_count)
            //     .sum();
            // let total_server: u64 = cache.guilds().len() as u64;

            let mut activities = vec![];

            if let Some(xau) = worm::services::market_ws::get_xauusd_display() {
                activities.push(ActivityData::custom(xau));
            }

            if !activities.is_empty() {
                let runners = shard_manager.runners.lock().await;
                for (_, runner) in runners.iter() {
                    runner.runner_tx.set_presence(
                        Some(activities[idx % activities.len()].clone()),
                        OnlineStatus::Online,
                    );
                }
                idx = (idx + 1) % activities.len();
            }
        }
    });

    tokio::time::sleep(tokio::time::Duration::from_millis(500)).await;

    let news_ws_url = env::var("NEWS_WS_URL").unwrap_or_else(|_| "ws://news-api:8000".to_string());
    let bot_id = env::var("CLIENT_ID").unwrap_or_else(|_| "discord-bot".to_string());
    start_news_ws_service(db_for_checker.clone(), http.clone(), news_ws_url.clone(), bot_id);
    println!(
        "[OK] News WebSocket service started (connecting to {})",
        news_ws_url
    );

    let price_ws_url = env::var("PRICE_WS_URL").unwrap_or_else(|_| "ws://localhost:4000".to_string());
    start_price_ws_service(db_for_checker, http.clone(), price_ws_url.clone());
    println!(
        "[OK] Price WebSocket service started (connecting to {})",
        price_ws_url
    );

    let stock_ws_url = env::var("STOCK_WS_URL").unwrap_or_else(|_| news_ws_url.clone());
    let http_for_stock = http.clone();
    let db_for_stock = db.clone();
    worm::services::init_stock_ws_client(&stock_ws_url, http_for_stock.clone(), db_for_stock);
    tokio::spawn(async move {
        if let Some(client) = worm::services::get_stock_ws_client_async().await {
            let _ = client.connect_and_listen().await;
        }
    });
    println!(
        "[OK] Stock News WebSocket service started (connecting to {})",
        stock_ws_url
    );

    client
        .start()
        .await
        .map_err(|e| BotError::Client(format!("Failed to initialize client: {}", e)))?;

    Ok(())
}
