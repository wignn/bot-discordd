import asyncio
import hashlib
from datetime import datetime, timezone, timedelta

from celery import shared_task
from sqlalchemy import text

from app.core.logging import get_logger
from app.db.session import get_sync_db
from workers.collectors.rss_collector import RSSCollector, DEFAULT_FOREX_FEEDS


logger = get_logger(__name__)

MAX_NEWS_AGE_HOURS = 2

_FEED_NAME_MAP = {feed["rss_url"]: feed["name"] for feed in DEFAULT_FOREX_FEEDS}


@shared_task(bind=True, max_retries=3)
def fetch_all_rss_feeds(self):
    async def _fetch():
        collector = RSSCollector()
        try:
            urls = [feed["rss_url"] for feed in DEFAULT_FOREX_FEEDS]
            results = await collector.fetch_multiple_feeds(urls, delay=0.2)
            
            total_entries = sum(len(entries) for entries in results.values())
            logger.info(
                "RSS feeds fetched",
                feeds_count=len(results),
                total_entries=total_entries,
            )
            
            for url, entries in results.items():
                for entry in entries:
                    process_rss_entry.delay(entry.__dict__, url)
            
            return {"feeds": len(results), "entries": total_entries}
        finally:
            await collector.close()
    
    return asyncio.run(_fetch())


@shared_task(bind=True, max_retries=3)
def fetch_single_feed(self, feed_url: str, source_id: str):
    async def _fetch():
        collector = RSSCollector()
        try:
            entries = await collector.fetch_feed(feed_url)
            
            for entry in entries:
                process_rss_entry.delay(entry.__dict__, feed_url, source_id)
            
            return {"entries": len(entries)}
        finally:
            await collector.close()
    
    return asyncio.run(_fetch())


@shared_task(bind=True)
def process_rss_entry(self, entry_data: dict, feed_url: str, source_id: str = None):
    from workers.tasks.scraping_tasks import scrape_article
    from workers.tasks.broadcast_tasks import broadcast_article
    
    url = entry_data.get("link", "")
    title = entry_data.get("title", "")
    content_hash = hashlib.sha256(f"{url}{title}".encode()).hexdigest()
    
    published_at = entry_data.get("published_at")
    if published_at:
        try:
            if isinstance(published_at, str):
                from dateutil import parser as date_parser
                published_at = date_parser.parse(published_at)
            
            if published_at.tzinfo is None:
                published_at = published_at.replace(tzinfo=timezone.utc)
            
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=MAX_NEWS_AGE_HOURS)
            if published_at < cutoff_time:
                return {"status": "skipped", "reason": "too_old", "url": url}
        except Exception:
            pass
    
    try:
        with get_sync_db() as session:
            result = session.execute(
                text("SELECT 1 FROM news_articles WHERE content_hash = :hash LIMIT 1"),
                {"hash": content_hash}
            )
            if result.scalar() is not None:
                return {"status": "skipped", "reason": "duplicate", "url": url}
    except Exception as e:
        logger.warning("Failed to check duplicate, processing anyway", error=str(e))
    
    logger.info("Processing RSS entry", title=title[:50], url=url)
    
    content = entry_data.get("content", "")
    description = entry_data.get("summary", "") or entry_data.get("description", "")
    
    if len(content) < 200:
        entry_data["source_name"] = _FEED_NAME_MAP.get(feed_url, "Unknown")
        scrape_article.delay(url, entry_data)
    else:
        source_name = _FEED_NAME_MAP.get(feed_url, "Unknown")
        
        broadcast_article.delay({
            "title": title,
            "content": content,
            "description": description,
            "url": url,
            "content_hash": content_hash,
            "published_at": entry_data.get("published_at"),
            "source_id": source_id,
            "source_name": source_name,
            "source_url": feed_url,
        })
    
    return {"status": "processed", "url": url}

