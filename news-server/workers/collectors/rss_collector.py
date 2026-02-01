import asyncio
import hashlib
from datetime import datetime, timezone
from typing import Any
from dataclasses import dataclass, field

import httpx
import feedparser
from dateutil import parser as date_parser

from app.core.config import settings
from app.core.logging import get_logger


logger = get_logger(__name__)


@dataclass
class RSSEntry:
    title: str
    link: str
    content: str
    published_at: datetime | None
    author: str | None
    tags: list[str]
    content_hash: str
    raw_entry: dict = field(default_factory=dict)


class RSSCollector:

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=settings.scraper_timeout,
            headers={"User-Agent": settings.scraper_user_agent},
            follow_redirects=True,
        )

    async def close(self):
        await self.client.aclose()

    async def fetch_feed(self, url: str) -> list[RSSEntry]:
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            
            feed = feedparser.parse(response.text)
            
            if feed.bozo and not feed.entries:
                logger.warning("Feed parsing error", url=url, error=str(feed.bozo_exception))
                return []

            entries = []
            for entry in feed.entries[:settings.rss_max_entries_per_feed]:
                parsed = self._parse_entry(entry)
                if parsed:
                    entries.append(parsed)

            logger.info(
                "Feed fetched successfully",
                url=url,
                entries_count=len(entries),
            )
            return entries

        except httpx.HTTPError as e:
            logger.error("HTTP error fetching feed", url=url, error=str(e))
            return []
        except Exception as e:
            logger.error("Error fetching feed", url=url, error=str(e))
            return []

    def _parse_entry(self, entry: dict) -> RSSEntry | None:
        try:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            
            if not title or not link:
                return None

            content = ""
            if "content" in entry:
                content = entry["content"][0].get("value", "")
            elif "summary" in entry:
                content = entry["summary"]
            elif "description" in entry:
                content = entry["description"]

            published_at = None
            if "published_parsed" in entry and entry["published_parsed"]:
                try:
                    published_at = datetime(*entry["published_parsed"][:6], tzinfo=timezone.utc)
                except Exception:
                    pass
            elif "published" in entry:
                try:
                    published_at = date_parser.parse(entry["published"])
                except Exception:
                    pass

            author = entry.get("author") or entry.get("author_detail", {}).get("name")
            tags = [tag.get("term", "") for tag in entry.get("tags", [])]

            hash_content = f"{title}|{link}|{content[:500]}"
            content_hash = hashlib.sha256(hash_content.encode()).hexdigest()

            return RSSEntry(
                title=title,
                link=link,
                content=content,
                published_at=published_at,
                author=author,
                tags=tags,
                content_hash=content_hash,
                raw_entry=entry,
            )

        except Exception as e:
            logger.warning("Error parsing entry", error=str(e))
            return None

    async def fetch_multiple_feeds(
        self,
        urls: list[str],
        delay: float = 1.0,
    ) -> dict[str, list[RSSEntry]]:
        results = {}
        
        for url in urls:
            entries = await self.fetch_feed(url)
            results[url] = entries
            
            if delay > 0:
                await asyncio.sleep(delay)

        return results


DEFAULT_FOREX_FEEDS = [
    {
        "name": "Reuters - Markets",
        "url": "https://www.reuters.com/markets",
        "rss_url": "https://www.rssboard.org/files/sample-rss-2.xml",
        "category": "general",
    },
    {
        "name": "ForexLive",
        "url": "https://www.forexlive.com",
        "rss_url": "https://www.forexlive.com/feed/news",
        "category": "forex",
    },
    {
        "name": "FXStreet",
        "url": "https://www.fxstreet.com",
        "rss_url": "https://www.fxstreet.com/rss/news",
        "category": "forex",
    },
    {
        "name": "DailyFX",
        "url": "https://www.dailyfx.com",
        "rss_url": "https://www.dailyfx.com/feeds/all",
        "category": "forex",
    },
    {
        "name": "Investing.com - Forex News",
        "url": "https://www.investing.com/news/forex-news",
        "rss_url": "https://www.investing.com/rss/news_301.rss",
        "category": "forex",
    },
    {
        "name": "Investing.com - Economic Indicators",
        "url": "https://www.investing.com/news/economic-indicators",
        "rss_url": "https://www.investing.com/rss/news_95.rss",
        "category": "economic",
    },
    {
        "name": "Federal Reserve",
        "url": "https://www.federalreserve.gov",
        "rss_url": "https://www.federalreserve.gov/feeds/press_all.xml",
        "category": "central_bank",
    },
    {
        "name": "ECB",
        "url": "https://www.ecb.europa.eu",
        "rss_url": "https://www.ecb.europa.eu/rss/press.html",
        "category": "central_bank",
    },
]
