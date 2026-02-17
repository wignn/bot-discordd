use crate::repository::VolatilityRepository;
use poise::serenity_prelude as serenity;
use serenity::{CreateEmbed, CreateEmbedFooter, Timestamp};

type Error = Box<dyn std::error::Error + Send + Sync>;
type Context<'a> = poise::Context<'a, super::Data, Error>;

#[poise::command(
    slash_command,
    prefix_command,
    guild_only,
    required_permissions = "ADMINISTRATOR"
)]
pub async fn volatility_setup(
    ctx: Context<'_>,
    #[description = "Channel for volatility alerts"] channel: serenity::GuildChannel,
) -> Result<(), Error> {
    let guild_id = ctx.guild_id().ok_or("Must be used in a guild")?.get();
    let channel_id = channel.id.get();

    let pool = ctx.data().db.as_ref();
    VolatilityRepository::insert_channel(pool, guild_id, channel_id).await?;

    let embed = CreateEmbed::default()
        .title("Gold Volatility Alert Setup")
        .description(format!(
            "Volatility spike alerts will be sent to <#{}>\n\n\
            **How it works:**\n\
            Monitors XAUUSD ATR (Average True Range) in real-time.\n\
            When current ATR exceeds 2x the historical average,\n\
            a warning is sent to this channel.\n\n\
            **Use case:**\n\
            Detect sudden gold volatility spikes before they hit the news.",
            channel_id
        ))
        .color(serenity::Colour::from_rgb(255, 215, 0))
        .footer(CreateEmbedFooter::new("Fio Volatility Detector"))
        .timestamp(Timestamp::now());

    ctx.send(poise::CreateReply::default().embed(embed)).await?;
    Ok(())
}

#[poise::command(
    slash_command,
    prefix_command,
    guild_only,
    required_permissions = "ADMINISTRATOR"
)]
pub async fn volatility_disable(ctx: Context<'_>) -> Result<(), Error> {
    let guild_id = ctx.guild_id().ok_or("Must be used in a guild")?.get();

    let pool = ctx.data().db.as_ref();
    VolatilityRepository::disable_channel(pool, guild_id).await?;

    let embed = CreateEmbed::default()
        .title("Volatility Alerts Disabled")
        .description(
            "Gold volatility spike alerts have been disabled.\n\nUse `/volatility_setup` to enable again.",
        )
        .color(serenity::Colour::from_rgb(158, 158, 158))
        .timestamp(Timestamp::now());

    ctx.send(poise::CreateReply::default().embed(embed)).await?;
    Ok(())
}

#[poise::command(slash_command, prefix_command, guild_only)]
pub async fn volatility_status(ctx: Context<'_>) -> Result<(), Error> {
    let guild_id = ctx.guild_id().ok_or("Must be used in a guild")?.get();

    let pool = ctx.data().db.as_ref();
    let channel = VolatilityRepository::get_channel(pool, guild_id).await?;

    let embed = match channel {
        Some(ch) => {
            let status = if ch.is_active { "Active" } else { "Disabled" };
            let color = if ch.is_active {
                serenity::Colour::from_rgb(255, 215, 0)
            } else {
                serenity::Colour::from_rgb(158, 158, 158)
            };

            CreateEmbed::default()
                .title("Gold Volatility Alert Status")
                .field("Status", status, true)
                .field("Channel", format!("<#{}>", ch.channel_id), true)
                .field("Symbol", "XAUUSD", true)
                .field("Threshold", "ATR > 2x Average", true)
                .color(color)
                .timestamp(Timestamp::now())
        }
        None => CreateEmbed::default()
            .title("Gold Volatility Alert Status")
            .description("Not configured. Use `/volatility_setup` to enable.")
            .color(serenity::Colour::from_rgb(158, 158, 158))
            .timestamp(Timestamp::now()),
    };

    ctx.send(poise::CreateReply::default().embed(embed)).await?;
    Ok(())
}
