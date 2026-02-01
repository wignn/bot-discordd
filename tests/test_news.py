#!/usr/bin/env python3
"""Unit tests for News Server forex functionality"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

# News event data structures
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class NewsEvent:
    """Test data structure matching news-server events"""
    id: str
    title: str
    title_id: Optional[str]
    summary: Optional[str]
    source_name: str
    source_url: str
    original_url: str
    sentiment: Optional[str]
    sentiment_confidence: Optional[float]
    impact_level: Optional[str]
    impact_score: Optional[int]
    currency_pairs: list
    currencies: list
    published_at: Optional[str]
    processed_at: str
    image_url: Optional[str]


class TestNewsEvent:
    """Test NewsEvent data structure"""
    
    def test_create_news_event(self):
        event = NewsEvent(
            id="test-123",
            title="Fed Announces Rate Decision",
            title_id="Fed Umumkan Keputusan Suku Bunga",
            summary="The Federal Reserve announced...",
            source_name="Reuters",
            source_url="https://reuters.com",
            original_url="https://reuters.com/article/123",
            sentiment="bearish",
            sentiment_confidence=0.85,
            impact_level="high",
            impact_score=8,
            currency_pairs=["EUR/USD", "GBP/USD"],
            currencies=["USD", "EUR", "GBP"],
            published_at="2026-02-01T07:00:00Z",
            processed_at="2026-02-01T07:01:00Z",
            image_url=None,
        )
        
        assert event.id == "test-123"
        assert event.sentiment == "bearish"
        assert event.impact_level == "high"
        assert len(event.currency_pairs) == 2
    
    def test_news_event_to_dict(self):
        event = NewsEvent(
            id="test-456",
            title="ECB Meeting",
            title_id=None,
            summary=None,
            source_name="Bloomberg",
            source_url="https://bloomberg.com",
            original_url="https://bloomberg.com/news/456",
            sentiment="neutral",
            sentiment_confidence=0.60,
            impact_level="medium",
            impact_score=5,
            currency_pairs=["EUR/USD"],
            currencies=["EUR"],
            published_at=None,
            processed_at="2026-02-01T08:00:00Z",
            image_url=None,
        )
        
        data = asdict(event)
        assert isinstance(data, dict)
        assert data["id"] == "test-456"
        assert data["source_name"] == "Bloomberg"


class TestDiscordEmbed:
    """Test Discord embed generation"""
    
    def create_discord_embed(self, event: NewsEvent) -> dict:
        """Generate Discord embed from news event"""
        color_map = {
            "bullish": 0x00FF00,
            "bearish": 0xFF0000,
            "neutral": 0x808080,
        }
        color = color_map.get(event.sentiment, 0x0099FF)
        
        impact_emoji = {
            "high": "🔴",
            "medium": "🟡",
            "low": "🟢",
        }
        
        fields = []
        
        if event.sentiment:
            confidence = f" ({event.sentiment_confidence:.0%})" if event.sentiment_confidence else ""
            fields.append({
                "name": "📊 Sentiment",
                "value": f"{event.sentiment.upper()}{confidence}",
                "inline": True,
            })
        
        if event.impact_level:
            emoji = impact_emoji.get(event.impact_level, "")
            fields.append({
                "name": "💥 Impact",
                "value": f"{emoji} {event.impact_level.upper()}",
                "inline": True,
            })
        
        if event.currency_pairs:
            fields.append({
                "name": "💱 Pairs",
                "value": ", ".join(event.currency_pairs[:5]),
                "inline": True,
            })
        
        return {
            "title": event.title_id or event.title,
            "description": f"Source: {event.source_name}",
            "url": event.original_url,
            "color": color,
            "fields": fields,
        }
    
    def test_bullish_embed_color(self):
        event = NewsEvent(
            id="1", title="Test", title_id=None, summary=None,
            source_name="Test", source_url="", original_url="",
            sentiment="bullish", sentiment_confidence=0.9,
            impact_level="high", impact_score=8,
            currency_pairs=["EUR/USD"], currencies=["USD"],
            published_at=None, processed_at="", image_url=None,
        )
        embed = self.create_discord_embed(event)
        assert embed["color"] == 0x00FF00  # Green
    
    def test_bearish_embed_color(self):
        event = NewsEvent(
            id="2", title="Test", title_id=None, summary=None,
            source_name="Test", source_url="", original_url="",
            sentiment="bearish", sentiment_confidence=0.8,
            impact_level="high", impact_score=8,
            currency_pairs=["EUR/USD"], currencies=["USD"],
            published_at=None, processed_at="", image_url=None,
        )
        embed = self.create_discord_embed(event)
        assert embed["color"] == 0xFF0000  # Red
    
    def test_embed_uses_translated_title(self):
        event = NewsEvent(
            id="3", title="Original Title", title_id="Judul Terjemahan",
            summary=None, source_name="Test", source_url="", original_url="",
            sentiment="neutral", sentiment_confidence=0.5,
            impact_level="low", impact_score=2,
            currency_pairs=[], currencies=[],
            published_at=None, processed_at="", image_url=None,
        )
        embed = self.create_discord_embed(event)
        assert embed["title"] == "Judul Terjemahan"
    
    def test_embed_fallback_to_original_title(self):
        event = NewsEvent(
            id="4", title="Original Title", title_id=None,
            summary=None, source_name="Test", source_url="", original_url="",
            sentiment="neutral", sentiment_confidence=0.5,
            impact_level="low", impact_score=2,
            currency_pairs=[], currencies=[],
            published_at=None, processed_at="", image_url=None,
        )
        embed = self.create_discord_embed(event)
        assert embed["title"] == "Original Title"


class TestImpactDetection:
    
    HIGH_IMPACT_KEYWORDS = [
        "breaking", "urgent", "fed", "fomc", "rate decision",
        "nfp", "non-farm", "gdp", "inflation", "cpi", "ppi",
        "central bank", "ecb", "boj", "intervention",
    ]
    
    MEDIUM_IMPACT_KEYWORDS = [
        "forecast", "outlook", "report", "data", "economic",
        "employment", "retail sales", "manufacturing",
    ]
    
    def detect_impact(self, title: str, description: str = "") -> str:
        text = (title + " " + description).lower()
        
        for keyword in self.HIGH_IMPACT_KEYWORDS:
            if keyword in text:
                return "high"
        
        for keyword in self.MEDIUM_IMPACT_KEYWORDS:
            if keyword in text:
                return "medium"
        
        return "low"
    
    def test_high_impact_fed(self):
        assert self.detect_impact("Fed Announces Emergency Rate Cut") == "high"
    
    def test_high_impact_nfp(self):
        assert self.detect_impact("NFP Report Shows Strong Job Growth") == "high"
    
    def test_high_impact_breaking(self):
        assert self.detect_impact("BREAKING: USD Falls After Announcement") == "high"
    
    def test_medium_impact_report(self):
        assert self.detect_impact("Weekly Economic Report Released") == "medium"
    
    def test_low_impact_generic(self):
        assert self.detect_impact("Market Summary for Today") == "low"


class TestCurrencyExtraction:
    """Test currency pair extraction from text"""
    
    FOREX_PAIRS = [
        "EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF",
        "AUD/USD", "NZD/USD", "USD/CAD",
        "EUR/GBP", "EUR/JPY", "GBP/JPY",
        "XAU/USD", "XAG/USD",
    ]
    
    CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CHF", "AUD", "NZD", "CAD"]
    
    def extract_pairs(self, text: str) -> list:
        """Extract currency pairs from text"""
        found = []
        text_upper = text.upper()
        
        for pair in self.FOREX_PAIRS:
            if pair in text_upper or pair.replace("/", "") in text_upper:
                found.append(pair)
        
        return list(set(found))
    
    def extract_currencies(self, text: str) -> list:
        """Extract individual currencies from text"""
        found = []
        text_upper = text.upper()
        
        for currency in self.CURRENCIES:
            if currency in text_upper:
                found.append(currency)
        
        return list(set(found))
    
    def test_extract_eurusd(self):
        pairs = self.extract_pairs("EUR/USD drops after Fed announcement")
        assert "EUR/USD" in pairs
    
    def test_extract_multiple_pairs(self):
        pairs = self.extract_pairs("EUR/USD and GBP/USD both fall on USD strength")
        assert "EUR/USD" in pairs
        assert "GBP/USD" in pairs
    
    def test_extract_without_slash(self):
        pairs = self.extract_pairs("EURUSD reaches new high")
        assert "EUR/USD" in pairs
    
    def test_extract_gold(self):
        pairs = self.extract_pairs("Gold XAU/USD surges on risk-off")
        assert "XAU/USD" in pairs
    
    def test_extract_currencies_from_text(self):
        currencies = self.extract_currencies("USD weakens against EUR and JPY")
        assert "USD" in currencies
        assert "EUR" in currencies
        assert "JPY" in currencies


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
