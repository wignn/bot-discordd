import asyncio
from celery import shared_task
from datetime import datetime, timezone, timedelta

from sqlalchemy import text

from app.core.logging import get_logger
from app.db.session import get_sync_db


logger = get_logger(__name__)

MAX_STOCK_NEWS_AGE_HOURS = 2


@shared_task(bind=True, max_retries=3)
def fetch_stock_id_feeds(self):
    from workers.collectors.stock_id_collector import StockIDCollector
    
    async def _fetch():
        collector = StockIDCollector()
        try:
            entries = await collector.fetch_latest(max_entries=30)
            
            logger.info("Stock feeds fetched", total=len(entries))
            
            for entry in entries:
                process_stock_entry.delay(entry.__dict__)
            
            return {"entries": len(entries)}
        finally:
            await collector.close()
    
    return asyncio.run(_fetch())


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def process_stock_entry(self, entry_data: dict):
    from app.stock.events import StockNewsEvent, broadcast_stock_news
    
    async def _process():
        try:
            content_hash = entry_data.get("content_hash", "")
            
            published_at_raw = entry_data.get("published_at")
            if published_at_raw:
                try:
                    if isinstance(published_at_raw, str):
                        from dateutil import parser as date_parser
                        pub_dt = date_parser.parse(published_at_raw)
                    else:
                        pub_dt = published_at_raw
                    
                    if pub_dt.tzinfo is None:
                        pub_dt = pub_dt.replace(tzinfo=timezone.utc)
                    
                    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=MAX_STOCK_NEWS_AGE_HOURS)
                    if pub_dt < cutoff_time:
                        return {"status": "skipped", "reason": "too_old", "hash": content_hash}
                except Exception:
                    pass
            
            try:
                with get_sync_db() as session:
                    result = session.execute(
                        text("SELECT 1 FROM stock_news WHERE content_hash = :hash LIMIT 1"),
                        {"hash": content_hash}
                    )
                    if result.scalar() is not None:
                        return {"status": "skipped", "reason": "duplicate", "hash": content_hash}
            except Exception as e:
                logger.warning("Failed to check stock duplicate", error=str(e))
            
            title = entry_data.get("title", "")
            content = entry_data.get("content", "")
            link = entry_data.get("link", "")
            source_name = entry_data.get("source_name", "Unknown")
            category = entry_data.get("category", "market")
            tickers = entry_data.get("tickers", [])
            
            summary = content[:500] if content else title
            sentiment = "neutral"
            
            if len(tickers) >= 3:
                impact_level = "high"
            elif len(tickers) >= 1:
                impact_level = "medium"
            else:
                impact_level = "low"
            
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
            
            await broadcast_stock_news(event)
            
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
                logger.warning("DB save failed", error=str(db_error))
            
            try:
                import httpx
                
                broadcast_data = {
                    "id": content_hash,
                    "original_title": title,
                    "translated_title": title,
                    "summary": summary,
                    "source_name": source_name,
                    "source_url": link,
                    "url": link,
                    "sentiment": sentiment,
                    "sentiment_confidence": 0.5,
                    "impact_level": impact_level,
                    "impact_score": 7 if impact_level == "high" else 5 if impact_level == "medium" else 3,
                    "currency_pairs": [],
                    "currencies": [],
                    "published_at": published_at,
                    "image_url": None,
                    "tickers": tickers,
                    "category": category,
                    "asset_type": "stock",
                }
                
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        "http://news-api:8000/api/v1/stream/ws/broadcast-article",
                        json=broadcast_data,
                    )
                    if response.status_code == 200:
                        result_data = response.json()
                        logger.info(
                            "Stock broadcast ok",
                            clients=result_data.get("clients_notified", 0),
                            title=title[:50] if title else "",
                        )
                    else:
                        logger.warning("Stock broadcast error", status=response.status_code)
            except Exception as http_error:
                logger.warning("Stock HTTP broadcast failed", error=str(http_error))
            
            logger.info("Stock processed", title=title[:50], tickers=tickers)
            
            return {"success": True, "hash": content_hash}
            
        except Exception as e:
            logger.error("Stock entry error", error=str(e))
            raise self.retry(exc=e)
    
    return asyncio.run(_process())


@shared_task
def schedule_stock_collection():
    fetch_stock_id_feeds.delay()
    logger.info("Stock collection scheduled")
