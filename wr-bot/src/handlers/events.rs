use crate::commands::Data;
use crate::repository::ModerationRepository;
use crate::utils::embed;
use serenity::all::{ChannelId, Context, CreateMessage, FullEvent, GuildId, Member, RoleId, User};

/// Main event handler for Discord events
pub async fn handle_event(
    ctx: &Context,
    event: &FullEvent,
    data: &Data,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    match event {
        FullEvent::VoiceStateUpdate { old, new } => {
            handle_voice_state_update(ctx, old, new, data).await?;
        }
        FullEvent::GuildMemberAddition { new_member } => {
            handle_member_join(ctx, new_member, data).await?;
        }
        FullEvent::GuildMemberRemoval {
            guild_id,
            user,
            member_data_if_available,
        } => {
            handle_member_leave(
                ctx,
                *guild_id,
                user,
                member_data_if_available.as_ref(),
                data,
            )
            .await?;
        }
        _ => {}
    }

    Ok(())
}

/// Handle voice state updates (join/leave voice channels)
async fn handle_voice_state_update(
    ctx: &Context,
    old: &Option<serenity::all::VoiceState>,
    new: &serenity::all::VoiceState,
    data: &Data,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    if let Ok(user) = ctx.http.get_user(new.user_id).await {
        if user.bot {
            return Ok(());
        }
    }

    let old_channel = old.as_ref().and_then(|vs| vs.channel_id);
    let new_channel = new.channel_id;

    if let Some(guild_id) = new.guild_id {
        handle_voice_logging(ctx, data, guild_id, old_channel, new_channel, new.user_id).await?;
    }

    Ok(())
}

/// Log voice channel join/leave events
async fn handle_voice_logging(
    ctx: &Context,
    data: &Data,
    guild_id: GuildId,
    old_channel: Option<ChannelId>,
    new_channel: Option<ChannelId>,
    user_id: serenity::all::UserId,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let pool = data.db.as_ref();
    let config = ModerationRepository::get_config(pool, guild_id.get()).await;

    if let Ok(Some(config)) = config {
        if let Some(log_channel_id) = config.log_channel_id {
            let log_channel = ChannelId::new(log_channel_id as u64);
            let user = ctx.http.get_user(user_id).await?;
            let avatar = user.avatar_url();

            // User joined a voice channel
            if new_channel.is_some() && old_channel != new_channel {
                if let Some(joined_channel_id) = new_channel {
                    let channel_name = get_channel_name(ctx, guild_id, joined_channel_id);
                    let embed_msg = embed::voice_join(
                        &user.name,
                        user.id.get(),
                        &channel_name,
                        avatar.as_deref(),
                    );
                    let message = CreateMessage::new().embed(embed_msg);
                    let _ = log_channel.send_message(&ctx.http, message).await;
                }
            }

            // User left a voice channel
            if old_channel.is_some() && old_channel != new_channel {
                if let Some(left_channel_id) = old_channel {
                    let channel_name = get_channel_name(ctx, guild_id, left_channel_id);
                    let embed_msg = embed::voice_leave(
                        &user.name,
                        user.id.get(),
                        &channel_name,
                        avatar.as_deref(),
                    );
                    let message = CreateMessage::new().embed(embed_msg);
                    let _ = log_channel.send_message(&ctx.http, message).await;
                }
            }
        }
    }

    Ok(())
}

/// Get channel name from cache or guild
fn get_channel_name(ctx: &Context, guild_id: GuildId, channel_id: ChannelId) -> String {
    ctx.cache
        .guild(guild_id)
        .and_then(|g| g.channels.get(&channel_id).map(|c| c.name.clone()))
        .unwrap_or_else(|| "Unknown".to_string())
}

/// Handle new member joining the server
async fn handle_member_join(
    ctx: &Context,
    new_member: &Member,
    data: &Data,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let guild_id = new_member.guild_id;

    let pool = data.db.as_ref();
    let config = ModerationRepository::get_config(pool, guild_id.get()).await;

    if let Ok(Some(config)) = config {
        if let Some(role_id) = config.auto_role_id {
            let role = RoleId::new(role_id as u64);
            let member = new_member.clone();
            if let Err(e) = member.add_role(&ctx.http, role).await {
                eprintln!("[MOD] Failed to assign auto-role: {}", e);
            }
        }

        if let Some(log_channel_id) = config.log_channel_id {
            let channel = ChannelId::new(log_channel_id as u64);
            let member_count = ctx
                .cache
                .guild(guild_id)
                .map(|g| g.member_count)
                .unwrap_or(0);

            let account_created = new_member
                .user
                .created_at()
                .format("%Y-%m-%d %H:%M UTC")
                .to_string();
            let avatar = new_member.user.avatar_url();

            let embed_msg = embed::member_join(
                &new_member.user.name,
                new_member.user.id.get(),
                member_count,
                avatar.as_deref(),
                &account_created,
            );

            let message = CreateMessage::new().embed(embed_msg);
            if let Err(e) = channel.send_message(&ctx.http, message).await {
                eprintln!("[MOD] Failed to send join log: {}", e);
            }
        }
    }

    Ok(())
}

/// Handle member leaving the server
async fn handle_member_leave(
    ctx: &Context,
    guild_id: GuildId,
    user: &User,
    _member_data: Option<&Member>,
    data: &Data,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let pool = data.db.as_ref();
    let config = ModerationRepository::get_config(pool, guild_id.get()).await;

    if let Ok(Some(config)) = config {
        if let Some(log_channel_id) = config.log_channel_id {
            let channel = ChannelId::new(log_channel_id as u64);

            let guild_name = ctx
                .cache
                .guild(guild_id)
                .map(|g| g.name.clone())
                .unwrap_or_else(|| "Server".to_string());

            let avatar = user.avatar_url();

            let embed_msg =
                embed::member_leave(&user.name, user.id.get(), avatar.as_deref(), &guild_name);

            let message = CreateMessage::new().embed(embed_msg);
            if let Err(e) = channel.send_message(&ctx.http, message).await {
                eprintln!("[MOD] Failed to send leave log: {}", e);
            }
        }
    }

    Ok(())
}
