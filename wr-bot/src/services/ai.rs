use std::collections::HashMap;
use std::time::Duration;
use serde::Deserialize;
use serde_json::json;
use tokio::time::sleep;

#[derive(Clone)]
pub struct Ai {
    base_url: String,
    api_key: String,
    model: String,
    prompt: String,
    history: HashMap<String, String>,
}

#[derive(Debug, Deserialize)]
struct ApiResponse {
    choices: Vec<Choice>,
}

#[derive(Debug, Deserialize)]
struct Choice {
    message: Message,
}

#[derive(Debug, Deserialize)]
struct Message {
    content: String,
}

impl Ai {
    pub fn new(base_url: String, api_key: String, model: String, prompt: String) -> Self {
        Self {
            base_url,
            api_key,
            model,
            prompt,
            history: HashMap::new(),
        }
    }

    pub async fn call_api(
        &mut self,
        user_input: String,
    ) -> Result<String, Box<dyn std::error::Error + Send + Sync>> {
        let client = reqwest::Client::new();
        let url = format!("{}/chat/completions", self.base_url);

        self.history.insert("user".to_string(), user_input.clone());

        let mut messages = vec![json!({"role": "system", "content": self.prompt})];

        for (role, content) in &self.history {
            messages.push(json!({
                "role": role,
                "content": content
            }));
        }

        let body = json!({
            "model": self.model,
            "max_tokens": 2000,
            "temperature": 0.7,
            "messages": messages
        });

        const MAX_ATTEMPTS: u32 = 5;
        let mut attempt: u32 = 0;

        loop {
            attempt += 1;

            let send_result = client
                .post(&url)
                .header("Authorization", format!("Bearer {}", self.api_key))
                .header("Content-Type", "application/json")
                .json(&body)
                .send()
                .await;

            match send_result {
                Ok(response) => {
                    let status = response.status();
                    if status.is_success() {
                        let api_response: ApiResponse = response.json().await?;
                        let reply = api_response.choices[0].message.content.clone();
                        self.history.insert("assistant".to_string(), reply.clone());
                        return Ok(reply);
                    }

                    // Handle rate-limiting specifically
                    if status.as_u16() == 429 && attempt < MAX_ATTEMPTS {
                        // Respect Retry-After header if present
                        if let Some(hv) = response.headers().get("retry-after") {
                            if let Ok(s) = hv.to_str() {
                                if let Ok(secs) = s.trim().parse::<u64>() {
                                    sleep(Duration::from_secs(secs)).await;
                                    continue;
                                }
                            }
                        }

                        // Fallback exponential backoff
                        let backoff_secs = 2u64.saturating_pow(attempt.min(6));
                        sleep(Duration::from_secs(backoff_secs)).await;
                        continue;
                    }

                    // Read response body for diagnostics (some providers return JSON error details)
                    let resp_text = match response.text().await {
                        Ok(t) => t,
                        Err(_) => String::from("<failed to read response body>"),
                    };
                    return Err(format!(
                        "API request failed with status: {}: {}",
                        status, resp_text
                    )
                    .into());
                }
                Err(e) => {
                    if attempt >= MAX_ATTEMPTS {
                        return Err(Box::new(e));
                    }
                    let backoff_secs = 2u64.saturating_pow(attempt.min(6));
                    sleep(Duration::from_secs(backoff_secs)).await;
                    continue;
                }
            }
        }
    }
}
