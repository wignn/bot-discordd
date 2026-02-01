import json
from dataclasses import dataclass, field

from workers.ai.providers.base import AIProvider, AIResponse
from workers.ai.providers.factory import get_ai_provider


@dataclass
class ExtractedEntities:
    currencies: list[str] = field(default_factory=list)
    currency_pairs: list[str] = field(default_factory=list)
    organizations: list[str] = field(default_factory=list)
    people: list[str] = field(default_factory=list)
    events: list[str] = field(default_factory=list)
    economic_indicators: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)


class EntityExtractor:

    def __init__(self, provider: AIProvider | None = None):
        self.provider = provider or get_ai_provider()

    async def extract(self, text: str) -> AIResponse:
        prompt = """Extract all named entities from this forex/financial news.

Output dalam format JSON:
{
    "currencies": ["USD", "EUR", "JPY"],
    "currency_pairs": ["EUR/USD", "USD/JPY"],
    "organizations": ["Federal Reserve", "ECB", "Bank of Japan"],
    "people": ["Jerome Powell", "Christine Lagarde"],
    "events": ["FOMC Meeting", "NFP Release", "ECB Rate Decision"],
    "economic_indicators": ["CPI", "GDP", "Unemployment Rate"],
    "locations": ["United States", "Eurozone", "Japan"],
    "numbers": {
        "rates": ["5.25%", "4.5%"],
        "prices": ["1.0850", "150.00"],
        "changes": ["+25 bps", "-0.5%"]
    }
}

News:
""" + text

        return await self.provider.generate(
            prompt=prompt,
            temperature=0.1,
            max_tokens=768,
        )

    async def extract_currency_pairs(self, text: str) -> list[str]:
        prompt = f"""List all forex currency pairs mentioned in this text.
Return as JSON array only. Example: ["EUR/USD", "GBP/JPY"]
If no pairs found, return empty array: []

Text: {text}"""

        response = await self.provider.generate(
            prompt=prompt,
            temperature=0.1,
            max_tokens=128,
        )

        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            return []

    async def extract_key_numbers(self, text: str) -> AIResponse:
        prompt = """Extract key numbers and statistics from this financial news.

Output dalam format JSON:
{
    "interest_rates": [{"value": "5.25%", "context": "Fed rate"}],
    "price_levels": [{"value": "1.0850", "context": "EUR/USD support"}],
    "economic_data": [{"indicator": "CPI", "value": "3.2%", "change": "+0.1%"}],
    "forecasts": [{"metric": "GDP growth", "value": "2.5%", "period": "Q4 2025"}]
}

News:
""" + text

        return await self.provider.generate(
            prompt=prompt,
            temperature=0.1,
            max_tokens=512,
        )
