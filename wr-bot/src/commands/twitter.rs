use crate::repository::TwitterRepository;
use poise::serenity_prelude as serenity;
use serenity::{CreateEmbed, CreateEmbedFooter, Timestamp};

type Error = Box<dyn std::error::Error + Send + Sync>;
type Context<'a> = poise::Context<'a, super::Data, Error>;

/// Setup X/Twitter feed channel
#[poise::command(
    slash_command,
    prefix_command,
    guild_only,
    required_permissions = "ADMINISTRATOR"
)]
pub async fn twitter_setup(
    ctx: Context<'_>,
    #[description = "Channel for X/Twitter feed"] channel: serenity::GuildChannel,
) -> Result<(), Error> {
    let guild_id = ctx.guild_id().ok_or("Must be used in a guild")?.get();
    let channel_id = channel.id.get();

    let pool = ctx.data().db.as_ref();
    TwitterRepository::insert_channel(pool, guild_id, channel_id).await?;

    let embed = CreateEmbed::default()
        .title("X/Twitter Feed Setup Complete")
        .description(format!(
            "Real-time X/Twitter feed will be sent to <#{}>\n\n\
            **How it works:**\n\
            Tweets from configured accounts will be posted here automatically.\n\n\
            **Note:**\n\
            Accounts to follow are configured server-side via `X_USERNAMES` env var.",
            channel_id
        ))
        .color(serenity::Colour::from_rgb(29, 161, 242))
        .footer(CreateEmbedFooter::new("X/Twitter Feed"))
        .timestamp(Timestamp::now());

    ctx.send(poise::CreateReply::default().embed(embed)).await?;
    Ok(())
}

/// Disable X/Twitter feed notifications
#[poise::command(
    slash_command,
    prefix_command,
    guild_only,
    required_permissions = "ADMINISTRATOR"
)]
pub async fn twitter_disable(ctx: Context<'_>) -> Result<(), Error> {
    let guild_id = ctx.guild_id().ok_or("Must be used in a guild")?.get();

    let pool = ctx.data().db.as_ref();
    TwitterRepository::disable_channel(pool, guild_id).await?;

    let embed = CreateEmbed::default()
        .title("X/Twitter Feed Disabled")
        .description(
            "X/Twitter feed notifications have been disabled.\n\nUse `/twitter_setup` to enable again.",
        )
        .color(serenity::Colour::from_rgb(158, 158, 158))
        .timestamp(Timestamp::now());

    ctx.send(poise::CreateReply::default().embed(embed)).await?;
    Ok(())
}

/// Enable X/Twitter feed notifications
#[poise::command(
    slash_command,
    prefix_command,
    guild_only,
    required_permissions = "ADMINISTRATOR"
)]
pub async fn twitter_enable(ctx: Context<'_>) -> Result<(), Error> {
    let guild_id = ctx.guild_id().ok_or("Must be used in a guild")?.get();

    let pool = ctx.data().db.as_ref();
    TwitterRepository::enable_channel(pool, guild_id).await?;

    let embed = CreateEmbed::default()
        .title("X/Twitter Feed Enabled")
        .description("X/Twitter feed notifications have been re-enabled.")
        .color(serenity::Colour::from_rgb(29, 161, 242))
        .timestamp(Timestamp::now());

    ctx.send(poise::CreateReply::default().embed(embed)).await?;
    Ok(())
}

/// Check X/Twitter feed status
#[poise::command(slash_command, prefix_command, guild_only)]
pub async fn twitter_status(ctx: Context<'_>) -> Result<(), Error> {
    let guild_id = ctx.guild_id().ok_or("Must be used in a guild")?.get();

    let pool = ctx.data().db.as_ref();
    let channel = TwitterRepository::get_channel(pool, guild_id).await?;

    let embed = match channel {
        Some(ch) => {
            let status = if ch.is_active { "Active" } else { "Disabled" };
            let color = if ch.is_active {
                serenity::Colour::from_rgb(29, 161, 242)
            } else {
                serenity::Colour::from_rgb(158, 158, 158)
            };

            CreateEmbed::default()
                .title("X/Twitter Feed Status")
                .field("Status", status, true)
                .field("Channel", format!("<#{}>", ch.channel_id), true)
                .color(color)
                .timestamp(Timestamp::now())
        }
        None => CreateEmbed::default()
            .title("X/Twitter Feed Status")
            .description("Not configured. Use `/twitter_setup` to enable.")
            .color(serenity::Colour::from_rgb(158, 158, 158))
            .timestamp(Timestamp::now()),
    };

    ctx.send(poise::CreateReply::default().embed(embed)).await?;
    Ok(())
}
