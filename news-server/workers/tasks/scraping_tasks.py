from celery import shared_task

from app.core.logging import get_logger


logger = get_logger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def scrape_article(self, url: str, rss_data: dict = None):
    import asyncio
    from workers.scrapers.generic_scraper import GenericScraper
    from workers.tasks.broadcast_tasks import broadcast_article  # Direct broadcast, no AI
    
    async def _scrape():
        scraper = GenericScraper()
        try:
            article = await scraper.scrape(url)
            
            if not article:
                logger.warning("Failed to scrape article", url=url)
                return {"status": "failed", "url": url}
            
            title = article.title
            content = article.content
            
            if rss_data:
                title = rss_data.get("title") or title
            
            # Get source info from RSS data
            source_name = rss_data.get("source_name", "Unknown") if rss_data else "Unknown"
            description = rss_data.get("summary", "") or rss_data.get("description", "") if rss_data else ""
            
            # Direct broadcast without AI processing (cost saving)
            broadcast_article.delay({
                "title": title,
                "content": content,
                "description": description,
                "url": url,
                "author": article.author,
                "published_at": str(article.published_at) if article.published_at else None,
                "image_url": article.image_url,
                "tags": article.tags,
                "content_hash": article.content_hash,
                "source_name": source_name,
            })
            
            logger.info(
                "Article scraped successfully",
                url=url,
                word_count=article.meta.get("word_count", 0),
            )
            
            return {"status": "success", "url": url}
            
        except Exception as e:
            logger.error("Scraping error", url=url, error=str(e))
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
                # Direct broadcast without AI processing (cost saving)
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
                    "source_name": "Unknown",
                })
            
            return {
                "status": "success",
                "total": len(urls),
                "scraped": len(articles),
            }
        finally:
            await scraper.close()
    
    return asyncio.run(_scrape())
