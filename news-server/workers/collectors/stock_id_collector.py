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


STOCK_KEYWORDS = [
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
]


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
    """Collector for Indonesian Stock Market News"""
    
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
        """Fetch and parse a single RSS feed"""
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
            for entry in feed.entries[:20]:  # Limit per feed
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
        """Parse RSS entry to StockNewsEntry"""
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

            # Clean content
            import re
            content = re.sub(r'<[^>]+>', '', content)
            content = content.strip()[:2000]  

            # Parse date
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

            # Get tags
            tags = []
            if "tags" in entry:
                tags = [tag.get("term", "") for tag in entry.get("tags", []) if tag.get("term")]

            # Generate hash
            hash_content = f"{title}{link}"
            content_hash = hashlib.md5(hash_content.encode()).hexdigest()

            # Extract tickers
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
        """Check if news is relevant to Indonesian stocks"""
        text = (entry.title + " " + entry.content).lower()
        
        # Check for stock keywords
        for keyword in STOCK_KEYWORDS:
            if keyword.lower() in text:
                return True
        
        # Check if has tickers
        if entry.tickers:
            return True
            
        return False

    def _extract_tickers(self, text: str) -> list[str]:
        """Extract Indonesian stock tickers from text"""
        import re
        
        # Common Indonesian stock tickers (4 uppercase letters)
        # Pattern: standalone 4-letter uppercase words
        pattern = r'\b([A-Z]{4})\b'
        
        potential_tickers = re.findall(pattern, text.upper())
        
        # Known Indonesian tickers for validation
        known_tickers = {
            "BBCA", "BBRI", "BMRI", "BBNI", "TLKM", "ASII", "UNVR", "HMSP",
            "GGRM", "ICBP", "INDF", "KLBF", "PGAS", "PTBA", "ADRO", "ANTM",
            "INCO", "MDKA", "GOTO", "BUKA", "ARTO", "BRIS", "BBTN", "SMGR",
            "INTP", "EXCL", "ISAT", "TOWR", "TBIG", "MNCN", "SCMA", "AKRA",
            "UNTR", "MEDC", "ESSA", "ACES", "MAPI", "ERAA", "SIDO", "KAEF",
            "CPIN", "JPFA", "MAIN", "SRIL", "TKIM", "INKP", "BRPT", "TPIA",
            "AMRT", "MIDI", "LPPF", "MYOR", "ROTI", "ULTJ", "MLBI", "DLTA",
            "IHSG", "JKSE",  # Index codes
        }
        
        # Filter to known tickers
        valid_tickers = [t for t in potential_tickers if t in known_tickers]
        
        return list(set(valid_tickers))

    async def fetch_all_feeds(self, delay: float = 1.0) -> dict[str, list[StockNewsEntry]]:
        """Fetch all Indonesian stock news feeds"""
        results = {}
        
        for feed_info in INDONESIA_STOCK_FEEDS:
            entries = await self.fetch_feed(feed_info)
            results[feed_info["name"]] = entries
            await asyncio.sleep(delay)  # Rate limiting
        
        return results

    async def fetch_latest(self, max_entries: int = 50) -> list[StockNewsEntry]:
        """Fetch latest stock news from all sources"""
        all_entries = []
        
        results = await self.fetch_all_feeds(delay=0.5)
        
        for entries in results.values():
            all_entries.extend(entries)
        
        # Sort by published date (newest first)
        all_entries.sort(
            key=lambda x: x.published_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True
        )
        
        # Remove duplicates by hash
        seen_hashes = set()
        unique_entries = []
        for entry in all_entries:
            if entry.content_hash not in seen_hashes:
                seen_hashes.add(entry.content_hash)
                unique_entries.append(entry)
        
        return unique_entries[:max_entries]
