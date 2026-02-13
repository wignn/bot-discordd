use std::env;
use std::fs;

#[derive(Clone, Debug)]
pub struct Config {
    pub token: String,
    pub client_id: String,
    pub prompt: String,
    pub scraping_base_url: String,
    pub openrouter_api_key: Option<String>,
    pub openrouter_model: String,
    pub openrouter_base_url: String,
    pub gemini_api_key: String,
    pub gemini_model: Option<String>,
    pub gemini_prompt: String,
}

impl Config {
    pub fn from_env() -> Result<Self, Box<dyn std::error::Error>> {
        let prompt_file = "system-prompt.txt";
        let prompt = fs::read_to_string(&prompt_file)
            .map_err(|e| format!("Failed to read prompt file '{}': {}", prompt_file, e))?;

        let token = env::var("TOKEN").map_err(|_| "TOKEN not configured in .env")?;
        let client_id = env::var("CLIENT_ID").map_err(|_| "CLIENT_ID not configured in .env")?;

        let openrouter_api_key = env::var("OPENROUTE_API_KEY").ok();
        let openrouter_model = env::var("OPENROUTE_MODEL")
            .unwrap_or_else(|_| "tngtech/deepseek-r1t2-chimera:free".to_string());
        let openrouter_base_url = env::var("OPENROUTE_BASE_URL")
            .unwrap_or_else(|_| "https://openrouter.ai/api/v1".to_string());

        let gemini_api_key = env::var("GEMINI_API_KEY").unwrap_or_else(|_| String::new());
        let gemini_model = env::var("GEMINI_MODEL").ok();

        let gemini_prompt_file = "gemini_prompt.txt";
        let gemini_prompt =
            fs::read_to_string(gemini_prompt_file).unwrap_or_else(|_| String::new());

        let scraping_base_url = env::var("FOREX_SERVICE_URL")
            .or_else(|_| env::var("SCRAPING_BASE_URL"))
            .unwrap_or_else(|_| "http://localhost:8000".to_string());

        Ok(Self {
            token,
            client_id,
            prompt,
            scraping_base_url,
            openrouter_api_key,
            openrouter_model,
            openrouter_base_url,
            gemini_api_key,
            gemini_model,
            gemini_prompt,
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
