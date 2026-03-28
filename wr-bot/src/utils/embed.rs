use poise::serenity_prelude::CreateEmbed;

pub const COLOR_SUCCESS: u32 = 0x2ECC71; // Green
pub const COLOR_ERROR: u32 = 0xE74C3C; // Red
pub const COLOR_WARNING: u32 = 0xF39C12; // Orange
pub const COLOR_INFO: u32 = 0x3498DB; // Blue

pub fn success(title: &str, description: &str) -> CreateEmbed {
    CreateEmbed::new()
        .title(format!("[OK] {}", title))
        .description(description)
        .color(COLOR_SUCCESS)
}

pub fn error(title: &str, description: &str) -> CreateEmbed {
    CreateEmbed::new()
        .title(format!("[ERROR] {}", title))
        .description(description)
        .color(COLOR_ERROR)
}

pub fn warning(title: &str, description: &str) -> CreateEmbed {
    CreateEmbed::new()
        .title(format!("[WARN] {}", title))
        .description(description)
        .color(COLOR_WARNING)
}

pub fn info(title: &str, description: &str) -> CreateEmbed {
    CreateEmbed::new()
        .title(title)
        .description(description)
        .color(COLOR_INFO)
}

pub const COLOR_JOIN: u32 = 0x43B581; // Green for joins
pub const COLOR_LEAVE: u32 = 0xF04747; // Red for leaves

pub fn member_join(
    username: &str,
    user_id: u64,
    member_count: u64,
    avatar_url: Option<&str>,
    guild_name: &str,
) -> CreateEmbed {
    let description = format!(
        "👋 **Welcome!**\n\nHai <@{}>, selamat datang di **{}**.\nKamu adalah member ke **{}**.",
        user_id, guild_name, member_count
    );

    let mut embed = CreateEmbed::new()
        .description(description)
        .color(0x5865F2)
        .footer(serenity::all::CreateEmbedFooter::new(format!(
            "WELCOME • {}",
            username
        )));

    if let Some(avatar) = avatar_url {
        embed = embed.thumbnail(avatar);
    }

    embed
}


pub fn member_leave(
    username: &str,
    member_count: u64,
    avatar_url: Option<&str>,
    guild_name: &str,
) -> CreateEmbed {
    let description = format!(
        "👋 **Goodbye**\n\n**{}** telah meninggalkan **{}**.\nMember tersisa: **{}**",
        username, guild_name, member_count
    );

    let mut embed = CreateEmbed::new()
        .description(description)
        .color(0xED4245)
        .footer(serenity::all::CreateEmbedFooter::new(format!(
            "GOODBYE • {}",
            username
        )));

    if let Some(avatar) = avatar_url {
        embed = embed.thumbnail(avatar);
    }

    embed
}


pub fn voice_join(
    username: &str,
    _user_id: u64,
    channel_name: &str,
    avatar_url: Option<&str>,
) -> CreateEmbed {
    let mut embed = CreateEmbed::new()
        .title("Joined Voice Channel")
        .description(format!("**{}** joined **{}**", username, channel_name))
        .color(COLOR_JOIN);

    if let Some(avatar) = avatar_url {
        embed = embed.thumbnail(avatar);
    }

    embed
}

pub fn voice_leave(
    username: &str,
    _user_id: u64,
    channel_name: &str,
    avatar_url: Option<&str>,
) -> CreateEmbed {
    let mut embed = CreateEmbed::new()
        .title("Left Voice Channel")
        .description(format!("**{}** left **{}**", username, channel_name))
        .color(COLOR_LEAVE);

    if let Some(avatar) = avatar_url {
        embed = embed.thumbnail(avatar);
    }

    embed
}
