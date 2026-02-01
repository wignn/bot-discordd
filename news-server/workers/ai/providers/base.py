from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal
from enum import Enum


class AITask(str, Enum):
    TRANSLATE = "translate"
    SUMMARIZE = "summarize"
    ANALYZE_SENTIMENT = "analyze_sentiment"
    EXTRACT_ENTITIES = "extract_entities"
    ANALYZE_IMPACT = "analyze_impact"
    GENERAL = "general"


@dataclass
class AIResponse:
    content: str
    model: str
    provider: str
    usage: dict[str, int] = field(default_factory=dict)
    raw_response: Any = None
    cached: bool = False
    latency_ms: float = 0.0

    @property
    def tokens_used(self) -> int:
        return self.usage.get("total_tokens", 0)


@dataclass
class AIMessage:
    role: Literal["system", "user", "assistant"]
    content: str


class AIProvider(ABC):

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self._client: Any = None

    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs,
    ) -> AIResponse:
        pass

    @abstractmethod
    async def chat(
        self,
        messages: list[AIMessage],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs,
    ) -> AIResponse:
        pass

    async def translate(
        self,
        text: str,
        target_language: str = "Indonesian",
        source_language: str = "English",
    ) -> AIResponse:
        prompt = f"""Translate the following text from {source_language} to {target_language}.
Keep the meaning accurate and natural sounding.
Only return the translation, nothing else.

Text to translate:
{text}"""
        return await self.generate(prompt, temperature=0.3, max_tokens=2048)

    async def summarize(
        self,
        text: str,
        max_sentences: int = 3,
        style: Literal["brief", "detailed", "bullet"] = "brief",
    ) -> AIResponse:
        style_instructions = {
            "brief": f"Summarize in {max_sentences} sentences or less.",
            "detailed": f"Provide a detailed summary in {max_sentences * 2} sentences.",
            "bullet": f"Summarize in {max_sentences} bullet points.",
        }

        prompt = f"""Summarize the following news article.
{style_instructions[style]}
Focus on key facts and market-relevant information.

Article:
{text}"""
        return await self.generate(prompt, temperature=0.3, max_tokens=512)

    async def analyze_sentiment(self, text: str) -> AIResponse:
        prompt = f"""Analyze the market sentiment of this forex/financial news.

Respond in this exact JSON format:
{{
    "sentiment": "bullish" | "bearish" | "neutral",
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation"
}}

News:
{text}"""
        return await self.generate(prompt, temperature=0.2, max_tokens=256)

    async def extract_entities(self, text: str) -> AIResponse:
        prompt = f"""Extract financial entities from this news article.

Respond in this exact JSON format:
{{
    "currencies": ["USD", "EUR"],
    "currency_pairs": ["EUR/USD"],
    "organizations": ["Federal Reserve"],
    "people": ["Jerome Powell"],
    "events": ["FOMC Meeting"],
    "indicators": ["NFP", "CPI"]
}}

News:
{text}"""
        return await self.generate(prompt, temperature=0.1, max_tokens=512)

    async def analyze_market_impact(self, text: str) -> AIResponse:
        prompt = f"""Analyze the potential market impact of this forex news.

Respond in this exact JSON format:
{{
    "impact_level": "high" | "medium" | "low",
    "affected_pairs": ["EUR/USD", "USD/JPY"],
    "short_term_outlook": "brief outlook",
    "trading_implication": "brief implication",
    "key_levels_to_watch": "any price levels mentioned"
}}

News:
{text}"""
        return await self.generate(prompt, temperature=0.3, max_tokens=512)

    async def health_check(self) -> bool:
        try:
            response = await self.generate("Say 'OK'", max_tokens=10)
            return bool(response.content)
        except Exception:
            return False
