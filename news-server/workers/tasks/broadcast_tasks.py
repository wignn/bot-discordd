import asyncio
import hashlib
import re
from celery import shared_task

from app.core.logging import get_logger


logger = get_logger(__name__)


def clean_html(html_content: str) -> str:
    content = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', html_content, flags=re.DOTALL)
    content = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', content, flags=re.DOTALL | re.IGNORECASE)
    paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', content, flags=re.DOTALL | re.IGNORECASE)
    
    if paragraphs:
        text = '\n\n'.join(paragraphs)
    else:
        text = content
    
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    
    text = text.replace('&amp;', '&')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&quot;', '"')
    text = text.replace('&#39;', "'")
    text = text.replace('&nbsp;', ' ')
    
    return text


def extract_summary(description: str, max_length: int = 500) -> str:
    text = clean_html(description)
    
    if len(text) > max_length:
        cut_pos = text.rfind('.', 0, max_length)
        if cut_pos > max_length // 2:
            text = text[:cut_pos + 1]
        else:
            text = text[:max_length].rsplit(' ', 1)[0] + '...'
    
    return text


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def broadcast_article(self, article_data: dict):
    async def _broadcast():
        try:
            title = article_data.get("title", "")
            content = article_data.get("content", "")
            description = article_data.get("description", "")
            url = article_data.get("url", "")
            content_hash = article_data.get("content_hash", "")
            
            summary = ""
            if description:
                summary = extract_summary(description, 500)
            elif content:
                summary = extract_summary(content, 500)
            
            broadcast_data = {
                "id": content_hash,
                "original_title": title,
                "translated_title": "",
                "summary": summary,
                "summary_id": "",
                "source_name": article_data.get("source_name", "Unknown"),
                "source_url": article_data.get("source_url", ""),
                "url": url,
                "sentiment": "neutral",
                "sentiment_confidence": 0.5,
                "impact_level": "medium",
                "impact_score": 5,
                "currency_pairs": [],
                "currencies": [],
                "published_at": article_data.get("published_at"),
                "image_url": article_data.get("image_url"),
            }
            
            try:
                from sqlalchemy import text
                from app.db.session import get_sync_db
                import uuid
                
                with get_sync_db() as session:
                    source_result = session.execute(
                        text("SELECT id FROM news_sources WHERE slug = 'default' LIMIT 1")
                    )
                    source_row = source_result.fetchone()
                    
                    if source_row:
                        source_id = source_row[0]
                    else:
                        new_source_id = str(uuid.uuid4())
                        session.execute(
                            text("""
                                INSERT INTO news_sources (id, name, slug, source_type, url, is_active)
                                VALUES (:id, 'Default Source', 'default', 'rss', 'https://example.com', TRUE)
                                ON CONFLICT (slug) DO NOTHING
                            """),
                            {"id": new_source_id}
                        )
                        session.commit()
                        source_id = new_source_id
                    
                    article_id = str(uuid.uuid4())
                    published_at = article_data.get("published_at")
                    source_name = article_data.get("source_name", "Unknown")
                    
                    session.execute(
                        text("""
                            INSERT INTO news_articles (id, source_id, content_hash, original_url, original_title, original_content, translated_title, summary, is_processed, processed_at, published_at, author)
                            VALUES (:id, :source_id, :hash, :url, :title, :content, :translated_title, :summary, TRUE, NOW(), :published_at, :author)
                            ON CONFLICT (content_hash) DO NOTHING
                        """),
                        {
                            "id": article_id,
                            "source_id": source_id,
                            "hash": content_hash,
                            "url": url,
                            "title": title,
                            "content": content[:5000] if content else "",
                            "translated_title": "",
                            "summary": summary,
                            "published_at": published_at,
                            "author": source_name,
                        }
                    )
                logger.info("Article saved", url=url[:50] if url else "")
            except Exception as db_error:
                logger.warning("DB save failed", error=str(db_error))
            
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
                            "Broadcast ok",
                            clients=result_data.get("clients_notified", 0),
                            title=title[:50] if title else "",
                        )
                    else:
                        logger.warning("Broadcast error", status=response.status_code)
                        
            except Exception as http_error:
                logger.warning("Broadcast failed", error=str(http_error))
            
            return {
                "status": "success",
                "url": url,
                "title": title[:50] if title else "",
                "broadcasted": True,
            }
            
        except Exception as e:
            logger.error(
                "Broadcast error",
                url=article_data.get("url"),
                error=str(e),
            )
            raise self.retry(exc=e)
    
    return asyncio.run(_broadcast())


@shared_task(bind=True)
def process_pending_articles(self):
    logger.info("Checking pending articles")
    return {"status": "completed", "processed": 0}
