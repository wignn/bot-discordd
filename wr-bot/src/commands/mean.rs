use poise::CreateReply;

use crate::{
    config::Config,
    error::BotError,
    services::ai::Ai,
};

fn split_into_chunks(s: &str, max: usize) -> Vec<String> {
    let mut chunks = Vec::new();
    let mut start = 0;
    let len = s.len();
    while start < len {
        let mut end = usize::min(start + max, len);
        while end > start && !s.is_char_boundary(end) {
            end -= 1;
        }
        if end == start {
            end = usize::min(start + max, len);
        }
        chunks.push(s[start..end].to_string());
        start = end;
    }
    chunks
}

type Error = Box<dyn std::error::Error + Send + Sync>;
type Context<'a> = poise::Context<'a, super::Data, Error>;

#[poise::command(prefix_command)]
pub async fn mean(ctx: Context<'_>) -> Result<(), Error> {
    let config = Config::from_env()
        .map_err(|e| BotError::Config(format!("Failed to load config: {}", e)))?;

    let api_key = match &config.api_key {
        Some(key) => key.clone(),
        None => {
            ctx.say("AI belum dikonfigurasi").await?;
            return Ok(());
        }
    };

    let prefix_ctx = match ctx {
        poise::Context::Prefix(p) => p,
        _ => {
            ctx.say("Command hanya tersedia untuk prefix").await?;
            return Ok(());
        }
    };

    let msg = prefix_ctx.msg;

    let referenced = match &msg.referenced_message {
        Some(m) => m,
        None => {
            ctx.say("Command harus reply ke message berita").await?;
            return Ok(());
        }
    };

    let embed = match referenced.embeds.first() {
        Some(e) => e,
        None => {
            ctx.say("Message tidak memiliki embed").await?;
            return Ok(());
        }
    };

    let title = embed.title.clone().unwrap_or_default();
    let description = embed.description.clone().unwrap_or_default();
    let url = embed.url.clone().unwrap_or_default();

    let analysis_prompt = format!(
        "Anda adalah analis makroekonomi dan valuta asing profesional.

Analisis berita berikut dan berikan:
1. Ringkasan yang jelas dalam 3-5 kalimat.
2. Penilaian dampak pasar (jangka pendek dan menengah).
3. Arah bias jika relevan (bullish/bearish/netral).
4. Faktor risiko yang perlu dipantau.

Data Berita:
Judul: {}
Deskripsi: {}
URL: {}",
        title, description, url
    );

    let mut ai = Ai::new(
        config.base_url,
        api_key,
        config.model_ai,
        config.prompt,
    );

    let loading_msg = ctx.say("Processing...").await?;

    const DISCORD_MAX_LEN: usize = 2000;
    const CHUNK_MAX: usize = 1900;

    let response = ai.call_api(analysis_prompt).await;
    let content = match response {
        Ok(res) => res,
        Err(e) => format!("AI error: {}", e),
    };

    if content.len() <= DISCORD_MAX_LEN {
        loading_msg
            .edit(ctx, CreateReply::default().content(content))
            .await?;
    } else {
        loading_msg
            .edit(
                ctx,
                CreateReply::default()
                    .content("Response terlalu panjang, dikirim terpisah"),
            )
            .await?;

        for chunk in split_into_chunks(&content, CHUNK_MAX) {
            ctx.say(chunk).await?;
        }
    }

    Ok(())
}
