use std::env;
use std::fs;

#[derive(Clone, Debug)]
pub struct Config {
    pub token: String,
    pub client_id: String,
    pub prompt: String,
    pub scraping_base_url: String,
}

impl Config {
    pub fn from_env() -> Result<Self, Box<dyn std::error::Error>> {

        let token = env::var("TOKEN").map_err(|_| "TOKEN not configured in .env")?;
        let client_id = env::var("CLIENT_ID").map_err(|_| "CLIENT_ID not configured in .env")?;

        let scraping_base_url = env::var("FOREX_SERVICE_URL")
            .or_else(|_| env::var("SCRAPING_BASE_URL"))
            .unwrap_or_else(|_| "http://localhost:8000".to_string());

        Ok(Self {
            token,
            client_id,
            prompt,
            scraping_base_url,
        })
    }

    pub fn is_openrouter_enabled(&self) -> bool {
        self.openrouter_api_key.is_some()
    }

    pub fn is_gemini_enabled(&self) -> bool {
        !self.gemini_api_key.is_empty()
    }

    pub fn is_ai_enabled(&self) -> bool {
        self.is_openrouter_enabled() || self.is_gemini_enabled()
    }
}
