import hashlib

from celery import shared_task

from app.core.logging import get_logger


logger = get_logger(__name__)


def _get_feed_name_from_url(url: str) -> str:
    if "fxstreet" in url.lower():
        return "FXStreet"
    elif "investing.com" in url.lower():
        return "Investing.com"
    elif "reuters" in url.lower():
        return "Reuters"
    elif "federalreserve" in url.lower():
        return "Federal Reserve"
    elif "ecb.europa" in url.lower():
        return "ECB"
    return "Unknown"


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def scrape_article(self, url: str, rss_data: dict = None):
    import asyncio
    from workers.scrapers.generic_scraper import GenericScraper
    from workers.tasks.broadcast_tasks import broadcast_article
    
    async def _scrape():
        scraper = GenericScraper()
        try:
            article = await scraper.scrape(url)
            
            if article:
                title = rss_data.get("title") or article.title if rss_data else article.title
                content = article.content
                source_name = rss_data.get("source_name", _get_feed_name_from_url(url)) if rss_data else _get_feed_name_from_url(url)
                description = rss_data.get("summary", "") or rss_data.get("description", "") if rss_data else ""
                published_at = str(article.published_at) if article.published_at else rss_data.get("published_at") if rss_data else None
                content_hash = article.content_hash
                
                broadcast_article.delay({
                    "title": title,
                    "content": content,
                    "description": description,
                    "url": url,
                    "author": article.author,
                    "published_at": published_at,
                    "image_url": article.image_url,
                    "tags": article.tags,
                    "content_hash": content_hash,
                    "source_name": source_name,
                })
                
                logger.info("Article scraped", url=url[:50])
                return {"status": "success", "url": url}
            
            if rss_data:
                logger.warning("Scraping failed, using RSS fallback", url=url[:50])
                title = rss_data.get("title", "")
                content = rss_data.get("content", "") or rss_data.get("summary", "") or rss_data.get("description", "")
                source_name = rss_data.get("source_name", _get_feed_name_from_url(url))
                content_hash = hashlib.sha256(f"{url}{title}".encode()).hexdigest()
                
                broadcast_article.delay({
                    "title": title,
                    "content": content,
                    "description": content,
                    "url": url,
                    "author": None,
                    "published_at": rss_data.get("published_at"),
                    "image_url": None,
                    "tags": rss_data.get("tags", []),
                    "content_hash": content_hash,
                    "source_name": source_name,
                })
                
                logger.info("RSS fallback broadcast", url=url[:50])
                return {"status": "fallback", "url": url}
            
            logger.warning("Failed to scrape, no fallback", url=url[:50])
            return {"status": "failed", "url": url}
            
        except Exception as e:
            logger.error("Scraping error", url=url[:50], error=str(e))
            
            if rss_data and self.request.retries >= self.max_retries - 1:
                title = rss_data.get("title", "")
                content = rss_data.get("content", "") or rss_data.get("summary", "") or rss_data.get("description", "")
                source_name = rss_data.get("source_name", _get_feed_name_from_url(url))
                content_hash = hashlib.sha256(f"{url}{title}".encode()).hexdigest()
                
                broadcast_article.delay({
                    "title": title,
                    "content": content,
                    "description": content,
                    "url": url,
                    "author": None,
                    "published_at": rss_data.get("published_at"),
                    "image_url": None,
                    "tags": rss_data.get("tags", []),
                    "content_hash": content_hash,
                    "source_name": source_name,
                })
                
                logger.info("Final retry fallback", url=url[:50])
                return {"status": "fallback", "url": url}
            
            raise self.retry(exc=e)
        finally:
            await scraper.close()
    
    return asyncio.run(_scrape())


@shared_task(bind=True, max_retries=2)
def scrape_batch(self, urls: list[str]):
    import asyncio
    from workers.scrapers.generic_scraper import GenericScraper
    
    async def _scrape():
        scraper = GenericScraper()
        try:
            articles = await scraper.scrape_batch(urls, delay=2.0)
            
            from workers.tasks.broadcast_tasks import broadcast_article
            
            for article in articles:
                broadcast_article.delay({
                    "title": article.title,
                    "content": article.content,
                    "description": "",
                    "url": article.url,
                    "author": article.author,
                    "published_at": str(article.published_at) if article.published_at else None,
                    "image_url": article.image_url,
                    "tags": article.tags,
                    "content_hash": article.content_hash,
                    "source_name": _get_feed_name_from_url(article.url),
                })
            
            return {
                "status": "success",
                "total": len(urls),
                "scraped": len(articles),
            }
        finally:
            await scraper.close()
    
    return asyncio.run(_scrape())
