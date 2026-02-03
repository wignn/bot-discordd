"""
Celery tasks for Indonesian Stock News collection and processing
"""

from celery import shared_task
from datetime import datetime, timezone

from app.core.logging import get_logger


logger = get_logger(__name__)


@shared_task(bind=True, max_retries=3)
def fetch_stock_id_feeds(self):
    """Fetch all Indonesian stock news feeds"""
    import asyncio
    from workers.collectors.stock_id_collector import StockIDCollector
    
    async def _fetch():
        collector = StockIDCollector()
        try:
            entries = await collector.fetch_latest(max_entries=30)
            
            logger.info(
                "Stock ID feeds fetched",
                total_entries=len(entries),
            )
            
            # Process each entry
            for entry in entries:
                process_stock_entry.delay(entry.__dict__)
            
            return {"entries": len(entries)}
        finally:
            await collector.close()
    
    return asyncio.run(_fetch())


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def process_stock_entry(self, entry_data: dict):
    """Process a single stock news entry with AI analysis"""
    import asyncio
    from workers.ai.processor import NewsProcessor
    from workers.ai.providers.factory import get_ai_provider
    from app.stock.events import StockNewsEvent, broadcast_stock_news
    
    async def _process():
        try:
            # Check if already processed (by hash)
            content_hash = entry_data.get("content_hash", "")
            
            # Skip duplicate check for now, process all
            
            title = entry_data.get("title", "")
            content = entry_data.get("content", "")
            link = entry_data.get("link", "")
            source_name = entry_data.get("source_name", "Unknown")
            category = entry_data.get("category", "market")
            tickers = entry_data.get("tickers", [])
            
            # AI Processing for summary and sentiment
            summary = content[:500] if content else title
            sentiment = "neutral"
            impact_level = "low"
            
            try:
                provider = get_ai_provider()
                processor = NewsProcessor(provider)
                
                result = await processor.process_article(
                    title=title,
                    content=content,
                    source_url=link,
                    translate=False,  # Already in Indonesian
                    analyze_sentiment=True,
                    analyze_impact=True,
                    extract_entities=False,
                )
                
                summary = result.summary or summary
                sentiment = result.sentiment or "neutral"
                impact_level = result.impact_level or "low"
                
            except Exception as ai_error:
                logger.warning("AI processing failed for stock news", error=str(ai_error))
            
            # Determine impact based on tickers
            if len(tickers) >= 3:
                impact_level = "high"
            elif len(tickers) >= 1:
                impact_level = "medium"
            
            # Create event
            published_at = entry_data.get("published_at")
            if isinstance(published_at, datetime):
                published_at = published_at.isoformat()
            
            event = StockNewsEvent(
                id=content_hash,
                title=title,
                summary=summary,
                content=content[:1000] if content else None,
                source_name=source_name,
                source_url=link,
                original_url=link,
                category=category,
                tickers=tickers,
                sentiment=sentiment,
                impact_level=impact_level,
                published_at=published_at,
                processed_at=datetime.now(timezone.utc).isoformat(),
            )
            
            # Broadcast to WebSocket
            await broadcast_stock_news(event)
            
            # Save to database
            try:
                from sqlalchemy import text
                from app.db.session import get_sync_db
                
                with get_sync_db() as session:
                    session.execute(
                        text("""
                            INSERT INTO stock_news (content_hash, original_url, title, summary, 
                                                   source_name, category, tickers, sentiment, 
                                                   impact_level, is_processed, processed_at)
                            VALUES (:hash, :url, :title, :summary, :source, :category, 
                                   :tickers, :sentiment, :impact, TRUE, NOW())
                            ON CONFLICT (content_hash) DO NOTHING
                        """),
                        {
                            "hash": content_hash,
                            "url": link,
                            "title": title,
                            "summary": summary,
                            "source": source_name,
                            "category": category,
                            "tickers": ",".join(tickers),
                            "sentiment": sentiment,
                            "impact": impact_level,
                        }
                    )
                    session.commit()
            except Exception as db_error:
                logger.warning("Failed to save stock news to DB", error=str(db_error))
            
            logger.info(
                "Stock news processed",
                title=title[:50],
                tickers=tickers,
                sentiment=sentiment,
            )
            
            return {"success": True, "hash": content_hash}
            
        except Exception as e:
            logger.error("Error processing stock entry", error=str(e))
            raise self.retry(exc=e)
    
    return asyncio.run(_process())


@shared_task
def schedule_stock_collection():
    """Schedule periodic stock news collection"""
    fetch_stock_id_feeds.delay()
    logger.info("Stock news collection scheduled")
