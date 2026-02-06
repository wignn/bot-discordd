import asyncio
from celery import shared_task

from app.core.logging import get_logger
from workers.collectors.calendar_collector import CalendarCollector


logger = get_logger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def check_calendar_reminders(self):
    async def _check():
        collector = CalendarCollector()
        try:
            events = await collector.get_upcoming_high_impact(
                minutes_before=15,
                minutes_window=5,
            )

            if not events:
                logger.debug("No upcoming high-impact events")
                return {"status": "completed", "events_found": 0, "broadcasted": 0}

            broadcasted = 0

            for event in events:
                try:
                    broadcast_data = {
                        "event_id": event.event_id,
                        "title": event.title,
                        "country": event.country,
                        "currency": event.currency,
                        "date_wib": event.date_wib,
                        "impact": event.impact,
                        "forecast": event.forecast,
                        "previous": event.previous,
                        "minutes_until": event.minutes_until(),
                    }

                    import httpx

                    async with httpx.AsyncClient(timeout=10.0) as client:
                        response = await client.post(
                            "http://news-api:8000/api/v1/stream/ws/broadcast-calendar",
                            json=broadcast_data,
                        )
                        if response.status_code == 200:
                            result_data = response.json()
                            logger.info(
                                "Calendar broadcast ok",
                                clients=result_data.get("clients_notified", 0),
                                event=event.title[:50],
                            )
                            broadcasted += 1
                        else:
                            logger.warning(
                                "Calendar broadcast error",
                                status=response.status_code,
                            )

                except Exception as e:
                    logger.warning(
                        "Failed to broadcast calendar event",
                        event=event.title,
                        error=str(e),
                    )

            return {
                "status": "completed",
                "events_found": len(events),
                "broadcasted": broadcasted,
            }

        except Exception as e:
            logger.error("Calendar reminder check failed", error=str(e))
            raise self.retry(exc=e)
        finally:
            await collector.close()

    return asyncio.run(_check())
