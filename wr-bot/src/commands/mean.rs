use poise::CreateReply;
use serde::Deserialize;

use crate::services::gemini::GeminiService;
use crate::{config::Config, error::BotError};

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

#[derive(Deserialize)]
struct ScrapedArticle {
    title: String,
    content: String,
    published_at: Option<String>,
    tags: Option<Vec<String>>,
}
type Error = Box<dyn std::error::Error + Send + Sync>;
type Context<'a> = poise::Context<'a, super::Data, Error>;

#[poise::command(prefix_command)]
pub async fn mean(ctx: Context<'_>) -> Result<(), Error> {
    let config = Config::from_env()
        .map_err(|e| BotError::Config(format!("Failed to load config: {}", e)))?;

    if !config.is_gemini_enabled() {
        ctx.say("Fitur Gemini AI belum dikonfigurasi. Harap set `GEMINI_API_KEY` di environment.")
            .await?;
        return Ok(());
    }

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

    let url: String = embed.url.clone().unwrap_or_default();

    let client = reqwest::Client::new();
    let scraping_endpoint = format!(
        "{}/api/v1/scraping",
        config.scraping_base_url.trim_end_matches('/')
    );

    let scrape_res = client
        .post(&scraping_endpoint)
        .json(&serde_json::json!({ "link": url }))
        .send()
        .await?;

    if !scrape_res.status().is_success() {
        let status = scrape_res.status();
        let body = scrape_res.text().await.unwrap_or_default();
        ctx.say(format!(
            "Gagal scraping berita. Status: {}, Body: {}",
            status, body
        ))
        .await?;
        return Ok(());
    }

    let article: ScrapedArticle = scrape_res.json().await?;
    let tags = article.tags.clone().unwrap_or_default();
    let published_at = article.published_at.clone().unwrap_or_default();

    const SYS_PROMPT: &str = "Anda adalah analis makroekonomi dan valuta asing profesional.
Gunakan pendekatan berbasis data, hindari opini spekulatif tanpa dasar.
Fokus pada implikasi kebijakan moneter, arus modal, yield obligasi, dan sentimen risiko global.
Gunakan bahasa formal dan ringkas.
";

    let analysis_prompt = format!(
        "Analisis berita berikut dan berikan:

1. Ringkasan yang jelas dalam 3-5 kalimat dan mudah dipahami orang awam.
2. Penilaian dampak pasar (jangka pendek dan menengah).
3. Arah bias jika relevan (bullish/bearish/netral).
4. Faktor risiko yang perlu dipantau.
buat jawabanya jadi paragraf jangan point point dan jangan ulangi kata yang saya kirim

Data Berita:
Judul: {}
Tanggal: {}
Tags: {:?}

Isi Berita:
{}

",
        article.title, published_at, tags, article.content
    );

    let gemini = GeminiService::new(
        config.gemini_api_key,
        config.gemini_model,
        SYS_PROMPT.to_string(),
    );

    let loading_msg = ctx.say("Processing...").await?;

    const DISCORD_MAX_LEN: usize = 2000;
    const CHUNK_MAX: usize = 1900;

    let response = gemini.generate(&analysis_prompt).await;
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
                CreateReply::default().content("Response terlalu panjang, dikirim terpisah"),
            )
            .await?;

        for chunk in split_into_chunks(&content, CHUNK_MAX) {
            ctx.say(chunk).await?;
        }
    }

    Ok(())
}
