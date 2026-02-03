import asyncio
from celery import shared_task

from app.core.logging import get_logger


logger = get_logger(__name__)


@shared_task(bind=True, max_retries=5, default_retry_delay=60)
def process_article_ai(self, article_data: dict):
    from workers.ai.processor import NewsProcessor
    from workers.ai.providers.factory import get_ai_provider
    
    async def _process():
        try:
            provider = get_ai_provider()
            processor = NewsProcessor(provider)
            
            result = await processor.process_article(
                title=article_data["title"],
                content=article_data["content"],
                source_url=article_data.get("url", ""),
            )
            
            logger.info(
                "Article processed",
                url=article_data.get("url"),
                tokens_used=result.tokens_used,
                processing_time_ms=result.processing_time_ms,
            )
            
            broadcast_data = {
                "id": article_data.get("content_hash", ""),
                "original_title": result.original_title or article_data.get("title", ""),
                "translated_title": result.translated_title,
                "summary": article_data.get("description", "") or article_data.get("content", "")[:500],
                "summary_id": result.summary,
                "source_name": article_data.get("source_name", "Unknown"),
                "source_url": article_data.get("source_url", ""),
                "url": article_data.get("url", ""),
                "sentiment": result.sentiment,
                "sentiment_confidence": result.sentiment_confidence,
                "impact_level": result.impact_level,
                "impact_score": result.impact_score,
                "currency_pairs": result.currency_pairs,
                "currencies": result.currencies,
                "published_at": article_data.get("published_at"),
                "image_url": article_data.get("image_url"),
            }
            
            try:
                from sqlalchemy import text
                from app.db.session import get_sync_db
                
                with get_sync_db() as session:
                    session.execute(
                        text("""
                            INSERT INTO news_articles (content_hash, original_url, original_title, original_content, translated_title, summary, is_processed, processed_at)
                            VALUES (:hash, :url, :title, :content, :translated_title, :summary, TRUE, NOW())
                            ON CONFLICT (content_hash) DO NOTHING
                        """),
                        {
                            "hash": article_data.get("content_hash", ""),
                            "url": article_data.get("url", ""),
                            "title": result.original_title,
                            "content": article_data.get("content", "")[:5000],
                            "translated_title": result.translated_title,
                            "summary": result.summary,
                        }
                    )
                logger.info("Article saved to database", url=article_data.get("url"))
            except Exception as db_error:
                logger.warning("Failed to save article to DB", error=str(db_error))
            
            try:
                import httpx
                
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        "http://news-api:8000/api/v1/stream/ws/broadcast-article",
                        json=broadcast_data,
                    )
                    if response.status_code == 200:
                        result_data = response.json()
                        logger.info(
                            "Broadcast via API",
                            clients_notified=result_data.get("clients_notified", 0),
                            high_impact=result_data.get("high_impact", False),
                        )
                    else:
                        logger.warning("Broadcast API error", status=response.status_code)
                        
            except Exception as http_error:
                logger.warning("Failed to broadcast via API", error=str(http_error))
            
            return {
                "status": "success",
                "url": article_data.get("url"),
                "sentiment": result.sentiment,
                "impact_level": result.impact_level,
                "tokens_used": result.tokens_used,
                "broadcasted": True,
            }
            
        except Exception as e:
            logger.error(
                "AI processing error",
                url=article_data.get("url"),
                error=str(e),
            )
            raise self.retry(exc=e)
    
    return asyncio.run(_process())


@shared_task(bind=True)
def process_pending_articles(self):
    logger.info("Checking for pending articles to process")
    return {"status": "completed", "processed": 0}


@shared_task(bind=True, max_retries=3)
def translate_article(self, article_id: str, text: str):
    import asyncio
    from workers.ai.translator import NewsTranslator
    from workers.ai.providers.factory import get_ai_provider
    
    async def _translate():
        provider = get_ai_provider()
        translator = NewsTranslator(provider)
        
        response = await translator.translate(text)
        
        return {
            "article_id": article_id,
            "translated": response.content[:100] + "...",
            "tokens_used": response.tokens_used,
        }
    
    return asyncio.run(_translate())


@shared_task(bind=True, max_retries=3)
def analyze_sentiment_task(self, article_id: str, text: str):
    import asyncio
    from workers.ai.sentiment_analyzer import SentimentAnalyzer
    from workers.ai.providers.factory import get_ai_provider
    
    async def _analyze():
        provider = get_ai_provider()
        analyzer = SentimentAnalyzer(provider)
        
        response = await analyzer.analyze(text)
        
        return {
            "article_id": article_id,
            "analysis": response.content,
            "tokens_used": response.tokens_used,
        }
    
    return asyncio.run(_analyze())


@shared_task(bind=True)
def reprocess_article(self, article_id: str):
    logger.info("Reprocessing article", article_id=article_id)
    return {"status": "queued", "article_id": article_id}
