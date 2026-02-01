from functools import lru_cache
from typing import Literal

from app.core.config import settings
from app.core.exceptions import ConfigurationException
from workers.ai.providers.base import AIProvider
from workers.ai.providers.groq_provider import GroqProvider
from workers.ai.providers.gemini_provider import GeminiProvider
from workers.ai.providers.openrouter_provider import OpenRouterProvider


ProviderName = Literal["groq", "gemini", "openrouter"]


class AIProviderFactory:

    _instances: dict[str, AIProvider] = {}

    @classmethod
    def create(
        cls,
        provider: ProviderName,
        model: str | None = None,
        api_key: str | None = None,
    ) -> AIProvider:
        if provider == "groq":
            key = api_key or settings.groq_api_key
            if not key:
                raise ConfigurationException("GROQ_API_KEY not configured")
            
            return GroqProvider(
                api_key=key,
                model=model or settings.groq_model_fast,
            )

        elif provider == "gemini":
            key = api_key or settings.gemini_api_key
            if not key:
                raise ConfigurationException("GEMINI_API_KEY not configured")
            
            return GeminiProvider(
                api_key=key,
                model=model or settings.gemini_model,
            )

        elif provider == "openrouter":
            key = api_key or settings.openrouter_api_key
            if not key:
                raise ConfigurationException("OPENROUTER_API_KEY not configured")
            
            return OpenRouterProvider(
                api_key=key,
                model=model or settings.openrouter_model,
                base_url=settings.openrouter_base_url,
            )

        else:
            raise ConfigurationException(f"Unknown provider: {provider}")

    @classmethod
    def get_cached(
        cls,
        provider: ProviderName,
        model: str | None = None,
    ) -> AIProvider:
        cache_key = f"{provider}:{model or 'default'}"
        
        if cache_key not in cls._instances:
            cls._instances[cache_key] = cls.create(provider, model)
        
        return cls._instances[cache_key]

    @classmethod
    def get_primary(cls) -> AIProvider:
        return cls.get_cached(settings.ai_primary_provider)

    @classmethod
    def clear_cache(cls) -> None:
        cls._instances.clear()


def get_ai_provider(
    provider: ProviderName | None = None,
    model: str | None = None,
) -> AIProvider:
    """
    Convenience function to get an AI provider
    
    Args:
        provider: Provider name (uses primary if None)
        model: Specific model to use
    
    Returns:
        AIProvider instance
    """
    if provider is None:
        return AIProviderFactory.get_primary()
    return AIProviderFactory.get_cached(provider, model)


# Convenience functions for specific providers
def get_groq(model: str | None = None) -> GroqProvider:
    """Get Groq provider"""
    return AIProviderFactory.get_cached("groq", model)  # type: ignore


def get_gemini(model: str | None = None) -> GeminiProvider:
    """Get Gemini provider"""
    return AIProviderFactory.get_cached("gemini", model)  # type: ignore


def get_openrouter(model: str | None = None) -> OpenRouterProvider:
    """Get OpenRouter provider"""
    return AIProviderFactory.get_cached("openrouter", model)  # type: ignore
