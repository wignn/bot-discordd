import os
from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_process_init

from app.core.config import settings

os.environ.setdefault("GRPC_ENABLE_FORK_SUPPORT", "0")
os.environ.setdefault("GRPC_POLL_STRATEGY", "epoll1")


celery_app = Celery(
    "news_intelligence",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "workers.tasks.collection_tasks",
        "workers.tasks.scraping_tasks",
        "workers.tasks.ai_tasks",
        "workers.tasks.maintenance_tasks",
        "workers.tasks.websocket_tasks",
        "workers.tasks.stock_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    
    timezone="UTC",
    enable_utc=True,
    
    task_track_started=True,
    task_time_limit=300,
    task_soft_time_limit=240,
    
    result_expires=3600,
    
    worker_prefetch_multiplier=1,
    worker_concurrency=4,
    
    task_annotations={
        "workers.tasks.ai_tasks.*": {
            "rate_limit": "30/m",
        },
    },
)

celery_app.conf.beat_schedule = {
    "fetch-rss-feeds": {
        "task": "workers.tasks.collection_tasks.fetch_all_rss_feeds",
        "schedule": crontab(minute="*/5"),
    },
    
    "fetch-stock-id-feeds": {
        "task": "workers.tasks.stock_tasks.fetch_stock_id_feeds",
        "schedule": crontab(minute="*/3"),  # Every 3 minutes for stock news
    },
    
    "process-pending-articles": {
        "task": "workers.tasks.ai_tasks.process_pending_articles",
        "schedule": crontab(minute="*/2"),
    },
    
    "websocket-heartbeat": {
        "task": "workers.tasks.websocket_tasks.send_heartbeat",
        "schedule": 30.0,
    },
    
    "broadcast-system-status": {
        "task": "workers.tasks.websocket_tasks.broadcast_system_status",
        "schedule": crontab(minute="*/5"),
    },
    
    "cleanup-old-data": {
        "task": "workers.tasks.maintenance_tasks.cleanup_old_articles",
        "schedule": crontab(hour=3, minute=0),
    },
    
    "update-source-stats": {
        "task": "workers.tasks.maintenance_tasks.update_source_statistics",
        "schedule": crontab(minute=0),
    },
}


@worker_process_init.connect
def init_worker_process(**kwargs):
    try:
        from workers.ai.providers.factory import AIProviderFactory
        AIProviderFactory.clear_cache()
    except Exception:
        pass
    
    # Re-configure Gemini after fork
    try:
        import google.generativeai as genai
        from app.core.config import settings
        if settings.gemini_api_key:
            genai.configure(api_key=settings.gemini_api_key)
    except Exception:
        pass


if __name__ == "__main__":
    celery_app.start()
