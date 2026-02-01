from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "news-intelligence-api"
    app_env: Literal["development", "staging", "production"] = "development"
    debug: bool = True
    secret_key: str = "change-me-in-production"

    # API Server
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4

    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/news_db"
    database_pool_size: int = 20
    database_max_overflow: int = 10

    redis_url: str = "redis://localhost:6379/0"
    redis_cache_ttl: int = 3600

    elasticsearch_url: str = "http://localhost:9200"
    elasticsearch_index_prefix: str = "news"

    celery_broker_url: str = "amqp://guest:guest@localhost:5672//"
    celery_result_backend: str = "redis://localhost:6379/1"

    ai_primary_provider: Literal["groq", "gemini", "openrouter"] = "groq"

    groq_api_key: str = ""
    groq_model_fast: str = "llama-3.1-8b-instant"
    groq_model_quality: str = "llama-3.1-70b-versatile"
    groq_model_mixtral: str = "mixtral-8x7b-32768"
    groq_rpm: int = 30
    groq_tpm: int = 6000

    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"
    gemini_rpm: int = 60
    gemini_tpd: int = 1500

    openrouter_api_key: str = ""
    openrouter_model: str = "meta-llama/llama-3.1-8b-instruct:free"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    scraper_user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    scraper_timeout: int = 30
    scraper_max_retries: int = 3
    scraper_delay_min: float = 1.0
    scraper_delay_max: float = 3.0

    rss_fetch_interval: int = 300
    rss_max_entries_per_feed: int = 50

    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "json"

    @computed_field
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @computed_field
    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
