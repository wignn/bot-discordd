import json
from typing import Literal

from workers.ai.providers.base import AIProvider, AIResponse
from workers.ai.providers.factory import get_ai_provider


SummaryStyle = Literal["brief", "detailed", "bullet", "forex_impact"]


class NewsSummarizer:

    def __init__(self, provider: AIProvider | None = None):
        self.provider = provider or get_ai_provider()

    async def summarize(
        self,
        text: str,
        style: SummaryStyle = "brief",
        language: str = "Indonesian",
    ) -> AIResponse:
        style_prompts = {
            "brief": "Buat ringkasan singkat dalam 2-3 kalimat.",
            "detailed": "Buat ringkasan lengkap dalam 5-6 kalimat.",
            "bullet": "Buat ringkasan dalam 4-5 poin bullet.",
            "forex_impact": "Fokus pada dampak untuk trading forex.",
        }

        prompt = f"""Ringkas artikel berita forex/finansial berikut dalam Bahasa Indonesia.

{style_prompts[style]}

Fokuskan pada:
- Fakta utama
- Dampak ke market
- Currency yang terpengaruh

Artikel:
{text}

Ringkasan:"""

        return await self.provider.generate(
            prompt=prompt,
            temperature=0.3,
            max_tokens=512,
        )

    async def summarize_for_trading(self, text: str) -> AIResponse:
        prompt = """Analisis berita forex ini dan buat ringkasan untuk trader.

Format output (JSON):
{
    "ringkasan": "2-3 kalimat ringkasan",
    "poin_utama": ["poin 1", "poin 2", "poin 3"],
    "dampak_market": "penjelasan singkat dampak",
    "pairs_terdampak": ["EUR/USD", "USD/JPY"],
    "sentimen": "bullish/bearish/netral",
    "rekomendasi": "saran singkat untuk trader"
}

Artikel:
""" + text

        return await self.provider.generate(
            prompt=prompt,
            temperature=0.3,
            max_tokens=768,
        )

    async def create_headline(self, text: str) -> AIResponse:
        prompt = f"""Buat headline menarik untuk artikel forex ini dalam Bahasa Indonesia.
Maksimal 15 kata. Harus informatif dan menarik perhatian trader.
Return HANYA headline, tanpa penjelasan.

Artikel:
{text}"""

        return await self.provider.generate(
            prompt=prompt,
            temperature=0.5,
            max_tokens=64,
        )
