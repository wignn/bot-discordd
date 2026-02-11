use crate::commands::Data;
use crate::utils::embed;
use poise::serenity_prelude::{self as serenity, CreateEmbed, Mentionable};
use serde::Deserialize;

type Error = Box<dyn std::error::Error + Send + Sync>;
type Context<'a> = poise::Context<'a, Data, Error>;

const VIDEO_SERVICE_URL: &str = "VIDEO_SERVICE_URL";
const DEFAULT_VIDEO_SERVICE: &str = "http://video-service:3100";

async fn send_embed(ctx: Context<'_>, embed: CreateEmbed) -> Result<(), Error> {
    ctx.send(poise::CreateReply::default().embed(embed)).await?;
    Ok(())
}

fn get_video_service_url() -> String {
    std::env::var(VIDEO_SERVICE_URL).unwrap_or_else(|_| DEFAULT_VIDEO_SERVICE.to_string())
}

#[derive(Deserialize)]
struct StreamStartResponse {
    success: Option<bool>,
    title: Option<String>,
    error: Option<String>,
}

#[derive(Deserialize)]
struct StreamStopResponse {
    success: Option<bool>,
    message: Option<String>,
    error: Option<String>,
}

#[derive(Deserialize)]
struct StreamStatusResponse {
    active: Option<bool>,
    title: Option<String>,
    duration: Option<u64>,
}

#[poise::command(slash_command, prefix_command)]
pub async fn watch(
    ctx: Context<'_>,
    #[description = "YouTube URL"] url: String,
) -> Result<(), Error> {
    let guild_id = match ctx.guild_id() {
        Some(id) => id,
        None => {
            send_embed(
                ctx,
                embed::error("Error", "This command can only be used in a server"),
            )
            .await?;
            return Ok(());
        }
    };

    let channel_id = {
        let guild = ctx.guild().ok_or("Cannot access guild")?;
        guild
            .voice_states
            .get(&ctx.author().id)
            .and_then(|vs| vs.channel_id)
    };

    let channel_id = match channel_id {
        Some(id) => id,
        None => {
            send_embed(
                ctx,
                embed::error("Error", "You need to be in a voice channel"),
            )
            .await?;
            return Ok(());
        }
    };

    // Validate URL
    if !url.contains("youtube.com") && !url.contains("youtu.be") && !url.starts_with("http") {
        send_embed(
            ctx,
            embed::error("Error", "Please provide a valid YouTube URL"),
        )
        .await?;
        return Ok(());
    }

    ctx.defer().await?;

    let base_url = get_video_service_url();
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(60))
        .build()?;

    let res = client
        .post(format!("{}/stream/start", base_url))
        .json(&serde_json::json!({
            "guild_id": guild_id.get().to_string(),
            "channel_id": channel_id.get().to_string(),
            "url": url,
        }))
        .send()
        .await;

    match res {
        Ok(response) => {
            if response.status().is_success() {
                let data: StreamStartResponse = response.json().await?;
                let title = data.title.unwrap_or_else(|| "Unknown".to_string());

                let embed_msg = CreateEmbed::new()
                    .title("Now Streaming")
                    .description(format!(
                        "**{}**\n\nStreaming via Go Live in {}",
                        title,
                        channel_id.mention()
                    ))
                    .field("URL", &url, false)
                    .color(0xFF0000)
                    .footer(serenity::CreateEmbedFooter::new(
                        "Use /stopwatch to stop streaming",
                    ));

                send_embed(ctx, embed_msg).await?;
            } else {
                let data: StreamStartResponse =
                    response.json().await.unwrap_or(StreamStartResponse {
                        success: Some(false),
                        title: None,
                        error: Some("Unknown error".to_string()),
                    });
                let err_msg = data
                    .error
                    .unwrap_or_else(|| "Failed to start stream".to_string());
                send_embed(ctx, embed::error("Stream Error", &err_msg)).await?;
            }
        }
        Err(e) => {
            eprintln!("[VIDEO] Failed to connect to video service: {}", e);
            send_embed(
                ctx,
                embed::error(
                    "Service Unavailable",
                    "Video streaming service is not available. Make sure it's running.",
                ),
            )
            .await?;
        }
    }

    Ok(())
}

#[poise::command(slash_command, prefix_command)]
pub async fn stopwatch(ctx: Context<'_>) -> Result<(), Error> {
    let guild_id = match ctx.guild_id() {
        Some(id) => id,
        None => {
            send_embed(
                ctx,
                embed::error("Error", "This command can only be used in a server"),
            )
            .await?;
            return Ok(());
        }
    };

    let base_url = get_video_service_url();
    let client = reqwest::Client::new();

    let res = client
        .post(format!("{}/stream/stop", base_url))
        .json(&serde_json::json!({
            "guild_id": guild_id.get().to_string(),
        }))
        .send()
        .await;

    match res {
        Ok(response) => {
            let data: StreamStopResponse = response.json().await.unwrap_or(StreamStopResponse {
                success: Some(false),
                message: None,
                error: Some("Unknown error".to_string()),
            });

            if data.success.unwrap_or(false) {
                send_embed(
                    ctx,
                    embed::info("Stream Stopped", "Video stream has been stopped"),
                )
                .await?;
            } else {
                let msg = data
                    .message
                    .or(data.error)
                    .unwrap_or_else(|| "No active stream".to_string());
                send_embed(ctx, embed::info("No Stream", &msg)).await?;
            }
        }
        Err(e) => {
            eprintln!("[VIDEO] Failed to connect to video service: {}", e);
            send_embed(
                ctx,
                embed::error(
                    "Service Unavailable",
                    "Video streaming service is not available",
                ),
            )
            .await?;
        }
    }

    Ok(())
}

#[poise::command(slash_command, prefix_command)]
pub async fn watchstatus(ctx: Context<'_>) -> Result<(), Error> {
    let guild_id = match ctx.guild_id() {
        Some(id) => id,
        None => {
            send_embed(
                ctx,
                embed::error("Error", "This command can only be used in a server"),
            )
            .await?;
            return Ok(());
        }
    };

    let base_url = get_video_service_url();
    let client = reqwest::Client::new();

    let res = client
        .get(format!("{}/stream/status/{}", base_url, guild_id.get()))
        .send()
        .await;

    match res {
        Ok(response) => {
            let data: StreamStatusResponse =
                response.json().await.unwrap_or(StreamStatusResponse {
                    active: Some(false),
                    title: None,
                    duration: None,
                });

            if data.active.unwrap_or(false) {
                let title = data.title.unwrap_or_else(|| "Unknown".to_string());
                let duration = data.duration.unwrap_or(0);
                let mins = duration / 60;
                let secs = duration % 60;

                let embed_msg = CreateEmbed::new()
                    .title("Stream Status")
                    .description(format!("**{}**", title))
                    .field("Duration", format!("{}:{:02}", mins, secs), true)
                    .field("Status", "Live", true)
                    .color(0xFF0000);

                send_embed(ctx, embed_msg).await?;
            } else {
                send_embed(
                    ctx,
                    embed::info("No Stream", "No video is currently streaming"),
                )
                .await?;
            }
        }
        Err(_) => {
            send_embed(
                ctx,
                embed::error(
                    "Service Unavailable",
                    "Video streaming service is not available",
                ),
            )
            .await?;
        }
    }

    Ok(())
}
