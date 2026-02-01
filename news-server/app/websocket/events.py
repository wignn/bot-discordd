from datetime import datetime
from typing import Any
from dataclasses import dataclass, asdict

from app.websocket.manager import ws_manager, EventType
from app.core.logging import get_logger


logger = get_logger(__name__)


@dataclass
class NewsEvent:
    id: str
    title: str
    title_id: str | None
    summary: str | None
    source_name: str
    source_url: str
    original_url: str
    
    sentiment: str | None
    sentiment_confidence: float | None
    impact_level: str | None
    impact_score: int | None
    
    currency_pairs: list[str]
    currencies: list[str]
    
    published_at: str | None
    processed_at: str
    image_url: str | None
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    def to_discord_embed(self) -> dict:
        color_map = {
            "bullish": 0x00FF00,
            "bearish": 0xFF0000,
            "neutral": 0x808080,
        }
        color = color_map.get(self.sentiment, 0x0099FF)
        
        impact_bars = {
            "high": "▰▰▰",
            "medium": "▰▰▱",
            "low": "▰▱▱",
        }
        impact_bar = impact_bars.get(self.impact_level, "▰▰▰")
        
        category = "MARKET"
        
        time_str = ""
        if self.published_at:
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(self.published_at.replace('Z', '+00:00'))
                time_str = dt.strftime("%H:%M WIB")
            except:
                time_str = "N/A"
        
        description_parts = [
            f"**{category}**",
            self.title_id or self.title,  # Use Indonesian title if available
            "",
            self.summary[:300] if self.summary else "",
        ]
        description = "\n".join(description_parts)
        
        fields = [
            {
                "name": "Waktu",
                "value": time_str or "N/A",
                "inline": True,
            },
            {
                "name": "Impact",
                "value": impact_bar,
                "inline": True,
            },
            {
                "name": "Sumber",
                "value": f"[Baca Selengkapnya]({self.original_url})",
                "inline": False,
            },
        ]
        
        footer_date = ""
        if self.published_at:
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(self.published_at.replace('Z', '+00:00'))
                footer_date = dt.strftime("%d/%m/%Y %H:%M")
            except:
                footer_date = ""
        
        # Use Indonesian title if available
        display_title = self.title_id or self.title
        
        return {
            "title": display_title,
            "description": description,
            "color": color,
            "fields": fields,
            "footer": {
                "text": f"Forex Alert • {self.source_name} • {footer_date}",
            },
        }


async def broadcast_new_article(article_data: dict) -> int:
    event = NewsEvent(
        id=article_data.get("id", ""),
        title=article_data.get("original_title", ""),
        title_id=article_data.get("translated_title"),
        summary=article_data.get("summary"),
        source_name=article_data.get("source_name", "Unknown"),
        source_url=article_data.get("source_url", ""),
        original_url=article_data.get("url", ""),
        sentiment=article_data.get("sentiment"),
        sentiment_confidence=article_data.get("sentiment_confidence"),
        impact_level=article_data.get("impact_level"),
        impact_score=article_data.get("impact_score"),
        currency_pairs=article_data.get("currency_pairs", []),
        currencies=article_data.get("currencies", []),
        published_at=article_data.get("published_at"),
        processed_at=datetime.utcnow().isoformat(),
        image_url=article_data.get("image_url"),
    )
    
    count = await ws_manager.broadcast(
        event=EventType.NEWS_NEW,
        data={
            "article": event.to_dict(),
            "discord_embed": event.to_discord_embed(),
        },
        channel="news",
    )
    
    logger.info(
        "Broadcasted new article",
        article_id=event.id,
        clients_notified=count,
    )
    
    return count


async def broadcast_high_impact_alert(article_data: dict) -> int:
    event = NewsEvent(
        id=article_data.get("id", ""),
        title=article_data.get("original_title", ""),
        title_id=article_data.get("translated_title"),
        summary=article_data.get("summary"),
        source_name=article_data.get("source_name", "Unknown"),
        source_url=article_data.get("source_url", ""),
        original_url=article_data.get("url", ""),
        sentiment=article_data.get("sentiment"),
        sentiment_confidence=article_data.get("sentiment_confidence"),
        impact_level="high",
        impact_score=article_data.get("impact_score", 8),
        currency_pairs=article_data.get("currency_pairs", []),
        currencies=article_data.get("currencies", []),
        published_at=article_data.get("published_at"),
        processed_at=datetime.utcnow().isoformat(),
        image_url=article_data.get("image_url"),
    )
    
    discord_embed = event.to_discord_embed()
    discord_embed["title"] = "HIGH IMPACT: " + discord_embed["title"]
    
    count = await ws_manager.broadcast(
        event=EventType.NEWS_HIGH_IMPACT,
        data={
            "article": event.to_dict(),
            "discord_embed": discord_embed,
            "alert": True,
            "mention_everyone": True,
        },
        channel="high_impact",
    )
    
    logger.info(
        "Broadcasted high impact alert",
        article_id=event.id,
        clients_notified=count,
    )
    
    return count


async def broadcast_sentiment_alert(
    currency_pair: str,
    sentiment: str,
    confidence: float,
    article_count: int,
    recent_articles: list[dict],
) -> int:
    data = {
        "currency_pair": currency_pair,
        "sentiment": sentiment,
        "confidence": confidence,
        "article_count": article_count,
        "recent_articles": recent_articles[:5],
        "timestamp": datetime.utcnow().isoformat(),
        "discord_embed": {
            "title": f"Sentiment Alert: {currency_pair}",
            "description": f"Market sentiment has shifted to **{sentiment.upper()}**",
            "color": 0x00FF00 if sentiment == "bullish" else 0xFF0000 if sentiment == "bearish" else 0x808080,
            "fields": [
                {"name": "Confidence", "value": f"{confidence:.0%}", "inline": True},
                {"name": "Based on", "value": f"{article_count} articles", "inline": True},
            ],
        },
    }
    
    return await ws_manager.broadcast(
        event=EventType.SENTIMENT_ALERT,
        data=data,
        channel="sentiment",
    )


async def broadcast_system_status(status: dict) -> int:
    return await ws_manager.broadcast(
        event=EventType.SYSTEM_STATUS,
        data={
            **status,
            "timestamp": datetime.utcnow().isoformat(),
        },
        channel="system",
    )
