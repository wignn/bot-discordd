import json
from typing import Literal
from dataclasses import dataclass

from workers.ai.providers.base import AIProvider, AIResponse
from workers.ai.providers.factory import get_ai_provider


@dataclass
class SentimentResult:
    sentiment: Literal["bullish", "bearish", "neutral"]
    confidence: float
    reasoning: str
    affected_currencies: list[str]
    raw_response: AIResponse


class SentimentAnalyzer:

    def __init__(self, provider: AIProvider | None = None):
        self.provider = provider or get_ai_provider()

    async def analyze(self, text: str) -> AIResponse:
        prompt = """Analisis sentimen market dari berita forex berikut.

Output dalam format JSON:
{
    "sentiment": "bullish" | "bearish" | "neutral",
    "confidence": 0.0-1.0,
    "reasoning": "alasan singkat",
    "affected_currencies": ["USD", "EUR"],
    "strength": "strong" | "moderate" | "weak",
    "timeframe": "short_term" | "medium_term" | "long_term"
}

Berita:
""" + text

        return await self.provider.generate(
            prompt=prompt,
            temperature=0.2,
            max_tokens=512,
        )

    async def analyze_for_pair(
        self,
        text: str,
        currency_pair: str,
    ) -> AIResponse:
        prompt = f"""Analisis sentimen untuk {currency_pair} berdasarkan berita ini.

Output dalam format JSON:
{{
    "pair": "{currency_pair}",
    "sentiment": "bullish" | "bearish" | "neutral",
    "confidence": 0.0-1.0,
    "direction": "buy {currency_pair}" | "sell {currency_pair}" | "wait",
    "reasoning": "alasan singkat",
    "key_levels": {{
        "support": "level support jika disebutkan",
        "resistance": "level resistance jika disebutkan"
    }}
}}

Berita:
{text}"""

        return await self.provider.generate(
            prompt=prompt,
            temperature=0.2,
            max_tokens=512,
        )

    async def batch_analyze(self, texts: list[str]) -> list[AIResponse]:
        results = []
        for text in texts:
            result = await self.analyze(text)
            results.append(result)
        return results

    async def aggregate_sentiment(
        self,
        analyses: list[dict],
    ) -> dict:
        if not analyses:
            return {
                "overall_sentiment": "neutral",
                "confidence": 0.5,
                "bullish_count": 0,
                "bearish_count": 0,
                "neutral_count": 0,
            }

        bullish = sum(1 for a in analyses if a.get("sentiment") == "bullish")
        bearish = sum(1 for a in analyses if a.get("sentiment") == "bearish")
        neutral = sum(1 for a in analyses if a.get("sentiment") == "neutral")

        total = len(analyses)
        
        if bullish > bearish and bullish > neutral:
            overall = "bullish"
            confidence = bullish / total
        elif bearish > bullish and bearish > neutral:
            overall = "bearish"
            confidence = bearish / total
        else:
            overall = "neutral"
            confidence = neutral / total if neutral > 0 else 0.5

        return {
            "overall_sentiment": overall,
            "confidence": confidence,
            "bullish_count": bullish,
            "bearish_count": bearish,
            "neutral_count": neutral,
            "total_analyzed": total,
        }
