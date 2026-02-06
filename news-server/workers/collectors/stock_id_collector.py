import asyncio
import hashlib
import re
from datetime import datetime, timezone
from typing import Any
from dataclasses import dataclass, field

import httpx
import feedparser
from dateutil import parser as date_parser

from app.core.config import settings
from app.core.logging import get_logger


logger = get_logger(__name__)


INDONESIA_STOCK_FEEDS = [
    {
        "name": "CNBC Indonesia - Market",
        "url": "https://www.cnbcindonesia.com/market",
        "rss_url": "https://www.cnbcindonesia.com/market/rss",
        "category": "market",
    },
    {
        "name": "Bisnis Indonesia - Market",
        "url": "https://market.bisnis.com",
        "rss_url": "https://www.bisnis.com/rss/market",
        "category": "market",
    },
    {
        "name": "Investing.com Indonesia - Market",
        "url": "https://id.investing.com",
        "rss_url": "https://id.investing.com/rss/news_25.rss",
        "category": "market",
    },
    {
        "name":"Tempo.co - Market",
        "url":"https://www.tempo.co",
        "rss_url":"https://rss.tempo.co/bisnis",
        "category":"market",
    }, {
        "name": "Detik - Market",
        "url": "https://finance.detik.com",
        "rss_url": "https://finance.detik.com/rss",
        "category": "market",
    },
    {
        "name":"cnn - market",
        "url":"https://www.cnnindonesia.com/ekonomi",
        "rss_url":"https://www.cnnindonesia.com/ekonomi/rss",
        "category":"market",
    }
]


STOCK_KEYWORDS = frozenset([
    "ihsg", "idx", "bei", "bursa efek", "saham", "emiten", "dividen",
    "ipo", "right issue", "stock split", "buyback", "tender offer",
    "listing", "delisting", "suspensi", "trading halt",
    "naik", "turun", "melemah", "menguat", "bullish", "bearish",
    "koreksi", "rally", "rebound", "profit taking", "window dressing",
    "laba", "rugi", "pendapatan", "omzet", "revenue", "net profit",
    "laporan keuangan", "kuartal", "semester", "tahunan",
    "eps", "per", "pbv", "roe", "roa", "der",
    "akuisisi", "merger", "divestasi", "spin off", "rights issue",
    "obligasi", "sukuk", "private placement",    
    "perbankan", "bank", "properti", "konstruksi", "tambang", "mining",
    "energi", "telekomunikasi", "consumer", "fmcg", "farmasi",
    "otomotif", "infrastruktur", "bumn",
    "bbca", "bbri", "bmri", "bbni", "tlkm", "asii", "unvr", "hmsp",
    "ggrm", "icbp", "indf", "klbf", "pgas", "ptba", "adro", "antm",
    "inco", "mdka", "goto", "buka", "arto", "bris",
])

TICKER_PATTERN = re.compile(r'\b([A-Z]{4})\b')

KNOWN_TICKERS = frozenset({
    "BBCA", "BBRI", "BMRI", "BBNI", "TLKM", "ASII", "UNVR", "HMSP",
    "GGRM", "ICBP", "INDF", "KLBF", "PGAS", "PTBA", "ADRO", "ANTM",
    "INCO", "MDKA", "GOTO", "BUKA", "ARTO", "BRIS", "BBTN", "SMGR",
    "INTP", "EXCL", "ISAT", "TOWR", "TBIG", "MNCN", "SCMA", "AKRA",
    "UNTR", "MEDC", "ESSA", "ACES", "MAPI", "ERAA", "SIDO", "KAEF",
    "CPIN", "JPFA", "MAIN", "SRIL", "TKIM", "INKP", "BRPT", "TPIA",
    "AMRT", "MIDI", "LPPF", "MYOR", "ROTI", "ULTJ", "MLBI", "DLTA",
    "IHSG", "JKSE",
})


@dataclass
class StockNewsEntry:
    title: str
    link: str
    content: str
    published_at: datetime | None
    author: str | None
    tags: list[str]
    content_hash: str
    source_name: str
    category: str
    tickers: list[str] = field(default_factory=list)
    raw_entry: dict = field(default_factory=dict)


class StockIDCollector:
    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
            },
            follow_redirects=True,
        )

    async def close(self):
        await self.client.aclose()

    async def fetch_feed(self, feed_info: dict) -> list[StockNewsEntry]:
        url = feed_info["rss_url"]
        source_name = feed_info["name"]
        category = feed_info["category"]
        
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            
            feed = feedparser.parse(response.text)
            
            if feed.bozo and not feed.entries:
                logger.warning("Feed parsing error", url=url, error=str(feed.bozo_exception))
                return []

            entries = []
            for entry in feed.entries[:20]:  
                parsed = self._parse_entry(entry, source_name, category)
                if parsed and self._is_relevant(parsed):
                    entries.append(parsed)

            logger.info(
                "Stock feed fetched",
                source=source_name,
                entries_count=len(entries),
            )
            return entries

        except httpx.HTTPError as e:
            logger.error("HTTP error fetching stock feed", url=url, error=str(e))
            return []
        except Exception as e:
            logger.error("Error fetching stock feed", url=url, error=str(e))
            return []

    def _parse_entry(self, entry: dict, source_name: str, category: str) -> StockNewsEntry | None:
        try:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            
            if not title or not link:
                return None

            content = ""
            if "content" in entry and entry["content"]:
                content = entry["content"][0].get("value", "")
            elif "summary" in entry:
                content = entry.get("summary", "")
            elif "description" in entry:
                content = entry.get("description", "")

            content = re.sub(r'<[^>]+>', '', content)
            content = content.strip()[:2000]  

            published_at = None
            for date_field in ["published", "updated", "created"]:
                if date_field in entry:
                    try:
                        published_at = date_parser.parse(entry[date_field])
                        if published_at.tzinfo is None:
                            published_at = published_at.replace(tzinfo=timezone.utc)
                        break
                    except Exception:
                        continue

            tags = []
            if "tags" in entry:
                tags = [tag.get("term", "") for tag in entry.get("tags", []) if tag.get("term")]

            hash_content = f"{title}{link}"
            content_hash = hashlib.md5(hash_content.encode()).hexdigest()

            tickers = self._extract_tickers(title + " " + content)

            return StockNewsEntry(
                title=title,
                link=link,
                content=content,
                published_at=published_at,
                author=entry.get("author"),
                tags=tags,
                content_hash=content_hash,
                source_name=source_name,
                category=category,
                tickers=tickers,
                raw_entry=entry,
            )

        except Exception as e:
            logger.error("Error parsing entry", error=str(e))
            return None

    def _is_relevant(self, entry: StockNewsEntry) -> bool:
        """Check if entry is relevant using optimized keyword matching."""
        if entry.tickers:
            return True
        
        text = (entry.title + " " + entry.content).lower()
        words = set(text.split())
        if words & STOCK_KEYWORDS:
            return True
        
        for keyword in STOCK_KEYWORDS:
            if " " in keyword and keyword in text:
                return True
            
        return False

    def _extract_tickers(self, text: str) -> list[str]:
        potential_tickers = TICKER_PATTERN.findall(text.upper())
        valid_tickers = set(potential_tickers) & KNOWN_TICKERS
        return list(valid_tickers)

    async def fetch_all_feeds(self, delay: float = 0.2) -> dict[str, list[StockNewsEntry]]:
        semaphore = asyncio.Semaphore(4)  
        async def fetch_with_limit(feed_info: dict) -> tuple[str, list[StockNewsEntry]]:
            async with semaphore:
                entries = await self.fetch_feed(feed_info)
                if delay > 0:
                    await asyncio.sleep(delay)
                return feed_info["name"], entries
        
        tasks = [fetch_with_limit(feed) for feed in INDONESIA_STOCK_FEEDS]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)
        
        results = {}
        for result in results_list:
            if isinstance(result, Exception):
                logger.warning("Stock feed fetch failed", error=str(result))
                continue
            name, entries = result
            results[name] = entries
        
        return results

    async def fetch_latest(self, max_entries: int = 50) -> list[StockNewsEntry]:
        """Fetch latest stock news from all sources"""
        all_entries = []
        
        results = await self.fetch_all_feeds(delay=0.5)
        
        for entries in results.values():
            all_entries.extend(entries)
        
        all_entries.sort(
            key=lambda x: x.published_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True
        )
        
        seen_hashes = set()
        unique_entries = []
        for entry in all_entries:
            if entry.content_hash not in seen_hashes:
                seen_hashes.add(entry.content_hash)
                unique_entries.append(entry)
        
        return unique_entries[:max_entries]
