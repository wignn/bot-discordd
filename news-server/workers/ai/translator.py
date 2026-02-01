import json
from typing import Literal

from workers.ai.providers.base import AIProvider, AIResponse
from workers.ai.providers.factory import get_ai_provider


class NewsTranslator:

    def __init__(self, provider: AIProvider | None = None):
        self.provider = provider or get_ai_provider()

    async def translate(
        self,
        text: str,
        target_language: str = "Indonesian",
        preserve_terms: bool = True,
    ) -> AIResponse:
        system_prompt = """You are an expert financial news translator.
Translate news articles accurately while maintaining the professional tone.
Keep financial terms, currency pairs (EUR/USD), and technical indicators in English.
Make the translation natural and easy to read."""

        prompt = f"""Translate the following financial news to {target_language}.

Rules:
1. Keep currency pairs like EUR/USD, GBP/JPY in original form
2. Keep technical terms like "NFP", "CPI", "FOMC", "hawkish", "dovish" in English
3. Keep organization names like "Federal Reserve", "ECB" in English  
4. Translate naturally, not word-by-word
5. Return ONLY the translation, no explanations

Text:
{text}"""

        return await self.provider.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=2048,
        )

    async def translate_title(self, title: str) -> AIResponse:
        prompt = f"""Translate this news title to Indonesian. Keep it concise and impactful.
Keep currency pairs and key financial terms in English.
Return ONLY the translated title.

Title: {title}"""

        return await self.provider.generate(
            prompt=prompt,
            temperature=0.3,
            max_tokens=256,
        )

    async def translate_batch(
        self,
        texts: list[str],
        target_language: str = "Indonesian",
    ) -> list[AIResponse]:
        results = []
        for text in texts:
            result = await self.translate(text, target_language)
            results.append(result)
        return results
