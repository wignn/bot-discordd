from celery import shared_task

from app.core.logging import get_logger


logger = get_logger(__name__)


@shared_task(bind=True, max_retries=3)
def fetch_all_rss_feeds(self):
    import asyncio
    from workers.collectors.rss_collector import RSSCollector, DEFAULT_FOREX_FEEDS
    
    async def _fetch():
        collector = RSSCollector()
        try:
            urls = [feed["rss_url"] for feed in DEFAULT_FOREX_FEEDS]
            results = await collector.fetch_multiple_feeds(urls, delay=1.0)
            
            total_entries = sum(len(entries) for entries in results.values())
            logger.info(
                "RSS feeds fetched",
                feeds_count=len(results),
                total_entries=total_entries,
            )
            
            # Queue articles for processing
            for url, entries in results.items():
                for entry in entries:
                    process_rss_entry.delay(entry.__dict__, url)
            
            return {"feeds": len(results), "entries": total_entries}
        finally:
            await collector.close()
    
    return asyncio.run(_fetch())


@shared_task(bind=True, max_retries=3)
def fetch_single_feed(self, feed_url: str, source_id: str):
    import asyncio
    from workers.collectors.rss_collector import RSSCollector
    
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
    import hashlib
    import asyncio
    from sqlalchemy import text
    from app.core.database import get_async_session
    from workers.tasks.scraping_tasks import scrape_article
    from workers.tasks.ai_tasks import process_article_ai
    
    # Generate content hash for deduplication
    url = entry_data.get("link", "")
    title = entry_data.get("title", "")
    content_hash = hashlib.sha256(f"{url}{title}".encode()).hexdigest()
    
    # Check if already processed
    async def check_exists():
        async for session in get_async_session():
            result = await session.execute(
                text("SELECT 1 FROM news_articles WHERE content_hash = :hash LIMIT 1"),
                {"hash": content_hash}
            )
            return result.scalar() is not None
    
    try:
        already_exists = asyncio.run(check_exists())
        if already_exists:
            logger.debug("Article already exists, skipping", url=url[:50])
            return {"status": "skipped", "reason": "duplicate", "url": url}
    except Exception as e:
        logger.warning("Failed to check duplicate, processing anyway", error=str(e))
    
    logger.info(
        "Processing RSS entry",
        title=title[:50],
        url=url,
    )
    
    content = entry_data.get("content", "")
    if len(content) < 500:
        scrape_article.delay(url, entry_data)
    else:
        process_article_ai.delay({
            "title": title,
            "content": content,
            "url": url,
            "content_hash": content_hash,
            "published_at": entry_data.get("published_at"),
            "source_id": source_id,
        })
    
    return {"status": "processed", "url": url}

