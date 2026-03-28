use std::env;

#[derive(Clone, Debug)]
pub struct Config {
    pub token: String,
    pub client_id: String,
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
            scraping_base_url,
        })
    }
}
