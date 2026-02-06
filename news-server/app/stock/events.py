from datetime import datetime
from typing import Any
from dataclasses import dataclass, asdict
from zoneinfo import ZoneInfo

from app.core.logging import get_logger

WIB = ZoneInfo("Asia/Jakarta")


logger = get_logger(__name__)


@dataclass
class StockNewsEvent:
    id: str
    title: str
    summary: str | None
    content: str | None
    
    source_name: str
    source_url: str
    original_url: str
    category: str
    
    tickers: list[str]
    
    sentiment: str | None
    impact_level: str | None
    
    published_at: str | None
    processed_at: str
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    def to_discord_embed(self) -> dict:
        color_map = {
            "bullish": 0x00FF00,
            "bearish": 0xFF0000,
            "neutral": 0x808080,
        }
        color = color_map.get(self.sentiment, 0x2962FF)
        
        impact_bars = {
            "high": "▰▰▰",
            "medium": "▰▰▱",
            "low": "▰▱▱",
        }
        impact_bar = impact_bars.get(self.impact_level, "▱▱▱")
        
        category_labels = {
            "market": "MARKET",
            "emiten": "EMITEN",
            "idx": "IDX",
            "corporate": "CORPORATE",
        }
        category_label = category_labels.get(self.category, "SAHAM")
        
        time_str = ""
        if self.published_at:
            try:
                dt = datetime.fromisoformat(self.published_at.replace('Z', '+00:00'))
                dt_wib = dt.astimezone(WIB)
                time_str = dt_wib.strftime("%H:%M WIB")
            except Exception:
                time_str = ""
        
        tickers_str = ""
        if self.tickers:
            tickers_str = " | " + ", ".join(self.tickers[:5])
        
        embed = {
            "title": self.title[:256],
            "description": "",
            "color": color,
            "fields": [],
            "footer": {
                "text": f"Stock Alert • {self.source_name} • {self.processed_at[:10]} {time_str}"
            },
        }
        
        header = f"**{category_label}**{tickers_str}"
        if self.title:
            header += f"\n{self.title}"
        
        embed["description"] = header
        
        if self.summary:
            embed["fields"].append({
                "name": "Ringkasan",
                "value": self.summary[:1024],
                "inline": False,
            })
        elif self.content:
            embed["fields"].append({
                "name": "Isi Berita",
                "value": self.content[:500] + "..." if len(self.content) > 500 else self.content,
                "inline": False,
            })
        
        embed["fields"].append({
            "name": "Waktu",
            "value": time_str or "N/A",
            "inline": True,
        })
        embed["fields"].append({
            "name": "Impact",
            "value": impact_bar,
            "inline": True,
        })
        
        embed["fields"].append({
            "name": "Sumber",
            "value": f"[Baca Selengkapnya]({self.original_url})",
            "inline": False,
        })
        
        return embed


class StockEventType:
    STOCK_NEW = "stock.new"
    STOCK_HIGH_IMPACT = "stock.high_impact"
    STOCK_TICKER_ALERT = "stock.ticker_alert"
    STOCK_SENTIMENT = "stock.sentiment"


async def broadcast_stock_news(event: StockNewsEvent):
    from app.stock.ws_manager import get_stock_ws_manager
    
    event_type = StockEventType.STOCK_NEW
    
    if event.impact_level == "high" or (event.tickers and len(event.tickers) >= 3):
        event_type = StockEventType.STOCK_HIGH_IMPACT
    
    manager = get_stock_ws_manager()
    await manager.broadcast(
        channel=event_type,
        data=event.to_dict(),
    )
    
    logger.info(
        "Stock news broadcasted",
        event_type=event_type,
        title=event.title[:50],
        tickers=event.tickers,
    )
