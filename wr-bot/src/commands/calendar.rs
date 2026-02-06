use crate::repository::CalendarRepository;
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
pub async fn calendar_setup(
    ctx: Context<'_>,
    #[description = "Channel for calendar reminders"] channel: serenity::GuildChannel,
) -> Result<(), Error> {
    let guild_id = ctx.guild_id().ok_or("Must be used in a guild")?.get();
    let channel_id = channel.id.get();

    let pool = ctx.data().db.as_ref();
    CalendarRepository::insert_channel(pool, guild_id, channel_id).await?;

    let embed = CreateEmbed::default()
        .title("Calendar Reminder Setup Complete")
        .description(format!(
            "High-impact economic event reminders will be sent to <#{}>\n\n\
            **Event Types:**\n\
            Central Bank Decisions, NFP, CPI, GDP, Interest Rate\n\n\
            **Timing:**\n\
            Reminders sent 15 minutes before each event\n\n\
            **Timezone:**\n\
            All times displayed in WIB (UTC+7)",
            channel_id
        ))
        .color(serenity::Colour::from_rgb(220, 53, 69))
        .footer(CreateEmbedFooter::new("Fio Calendar"))
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
pub async fn calendar_disable(ctx: Context<'_>) -> Result<(), Error> {
    let guild_id = ctx.guild_id().ok_or("Must be used in a guild")?.get();

    let pool = ctx.data().db.as_ref();
    CalendarRepository::disable_channel(pool, guild_id).await?;

    let embed = CreateEmbed::default()
        .title("Calendar Reminders Disabled")
        .description(
            "Calendar reminder notifications have been disabled.\n\nUse `/calendar_setup` to enable again.",
        )
        .color(serenity::Colour::from_rgb(158, 158, 158))
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
pub async fn calendar_enable(ctx: Context<'_>) -> Result<(), Error> {
    let guild_id = ctx.guild_id().ok_or("Must be used in a guild")?.get();

    let pool = ctx.data().db.as_ref();
    CalendarRepository::enable_channel(pool, guild_id).await?;

    let embed = CreateEmbed::default()
        .title("Calendar Reminders Enabled")
        .description("Calendar reminder notifications have been re-enabled.")
        .color(serenity::Colour::from_rgb(220, 53, 69))
        .timestamp(Timestamp::now());

    ctx.send(poise::CreateReply::default().embed(embed)).await?;
    Ok(())
}

#[poise::command(slash_command, prefix_command, guild_only)]
pub async fn calendar_status(ctx: Context<'_>) -> Result<(), Error> {
    let guild_id = ctx.guild_id().ok_or("Must be used in a guild")?.get();

    let pool = ctx.data().db.as_ref();
    let channel = CalendarRepository::get_channel(pool, guild_id).await?;

    let embed = match channel {
        Some(ch) => {
            let status = if ch.is_active { "Active" } else { "Disabled" };
            let color = if ch.is_active {
                serenity::Colour::from_rgb(220, 53, 69)
            } else {
                serenity::Colour::from_rgb(158, 158, 158)
            };

            CreateEmbed::default()
                .title("Calendar Reminder Status")
                .field("Status", status, true)
                .field("Channel", format!("<#{}>", ch.channel_id), true)
                .field(
                    "Mention Everyone",
                    if ch.mention_everyone { "Yes" } else { "No" },
                    true,
                )
                .color(color)
                .timestamp(Timestamp::now())
        }
        None => CreateEmbed::default()
            .title("Calendar Reminder Status")
            .description("Not configured. Use `/calendar_setup` to enable.")
            .color(serenity::Colour::from_rgb(158, 158, 158))
            .timestamp(Timestamp::now()),
    };

    ctx.send(poise::CreateReply::default().embed(embed)).await?;
    Ok(())
}

#[poise::command(
    slash_command,
    prefix_command,
    guild_only,
    required_permissions = "ADMINISTRATOR"
)]
pub async fn calendar_mention(
    ctx: Context<'_>,
    #[description = "Enable @everyone mention"] enable: bool,
) -> Result<(), Error> {
    let guild_id = ctx.guild_id().ok_or("Must be used in a guild")?.get();

    let pool = ctx.data().db.as_ref();
    CalendarRepository::set_mention_everyone(pool, guild_id, enable).await?;

    let status = if enable { "enabled" } else { "disabled" };
    let embed = CreateEmbed::default()
        .title("Mention Setting Updated")
        .description(format!(
            "@everyone mention for high-impact events has been {}.",
            status
        ))
        .color(serenity::Colour::from_rgb(220, 53, 69))
        .timestamp(Timestamp::now());

    ctx.send(poise::CreateReply::default().embed(embed)).await?;
    Ok(())
}
