import json
from typing import Literal
from dataclasses import dataclass

from workers.ai.providers.base import AIProvider, AIResponse
from workers.ai.providers.factory import get_ai_provider


ImpactLevel = Literal["high", "medium", "low", "none"]


@dataclass
class ImpactAnalysis:
    impact_level: ImpactLevel
    affected_pairs: list[str]
    direction: dict[str, str]
    confidence: float
    reasoning: str


class ImpactAnalyzer:

    def __init__(self, provider: AIProvider | None = None):
        self.provider = provider or get_ai_provider()

    async def analyze(self, text: str) -> AIResponse:
        prompt = """Analisis dampak market dari berita forex ini.

Output dalam format JSON:
{
    "impact_level": "high" | "medium" | "low",
    "impact_score": 1-10,
    "affected_pairs": [
        {
            "pair": "EUR/USD",
            "direction": "bullish" | "bearish",
            "expected_move": "50-100 pips",
            "confidence": 0.0-1.0
        }
    ],
    "timeframe": {
        "immediate": "reaksi 0-1 jam",
        "short_term": "reaksi 1-24 jam",
        "medium_term": "reaksi 1-7 hari"
    },
    "key_levels": {
        "EUR/USD": {
            "support": ["1.0800", "1.0750"],
            "resistance": ["1.0900", "1.0950"]
        }
    },
    "trading_recommendation": {
        "action": "buy" | "sell" | "wait",
        "reasoning": "alasan singkat",
        "risk_level": "high" | "medium" | "low"
    },
    "related_events": ["event yang mungkin terpengaruh"],
    "reasoning": "penjelasan lengkap dampak"
}

Berita:
""" + text

        return await self.provider.generate(
            prompt=prompt,
            temperature=0.3,
            max_tokens=1024,
        )

    async def quick_impact_score(self, text: str) -> AIResponse:
        prompt = f"""Rate the market impact of this forex news from 1-10.

Rules:
- 9-10: Major central bank decision, unexpected rate change
- 7-8: Important economic data (NFP, CPI), policy signals
- 5-6: Moderate economic data, official speeches
- 3-4: Minor data, general market commentary  
- 1-2: Little to no market impact

Return JSON only:
{{"score": 7, "reason": "brief reason"}}

News: {text}"""

        return await self.provider.generate(
            prompt=prompt,
            temperature=0.2,
            max_tokens=128,
        )

    async def compare_to_expectations(
        self,
        actual: str,
        expected: str,
        indicator: str,
    ) -> AIResponse:
        prompt = f"""Analisis apakah data ekonomi ini beat atau miss expectations.

Indikator: {indicator}
Actual: {actual}
Expected: {expected}

Output JSON:
{{
    "result": "beat" | "miss" | "inline",
    "deviation": "perbedaan dari ekspektasi",
    "market_reaction": "prediksi reaksi market",
    "affected_currency": "mata uang yang terpengaruh",
    "impact_direction": "bullish" | "bearish" | "neutral"
}}"""

        return await self.provider.generate(
            prompt=prompt,
            temperature=0.2,
            max_tokens=256,
        )
