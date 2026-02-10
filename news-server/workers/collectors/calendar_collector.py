import httpx
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from zoneinfo import ZoneInfo
from typing import ClassVar

from app.core.logging import get_logger
from app.core.config import settings


logger = get_logger(__name__)

FOREX_FACTORY_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

WIB = ZoneInfo("Asia/Jakarta")

CALENDAR_CACHE_TTL = timedelta(hours=2)


@dataclass
class CalendarEvent:
    title: str
    country: str
    currency: str
    date_utc: datetime
    date_wib: str
    impact: str
    forecast: str
    previous: str
    event_id: str

    def minutes_until(self) -> int:
        now = datetime.now(timezone.utc)
        delta = self.date_utc - now
        return int(delta.total_seconds() / 60)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "country": self.country,
            "currency": self.currency,
            "date_utc": self.date_utc.isoformat(),
            "date_wib": self.date_wib,
            "impact": self.impact,
            "forecast": self.forecast,
            "previous": self.previous,
            "event_id": self.event_id,
            "minutes_until": self.minutes_until(),
        }


class CalendarCollector:
    # Class-level cache shared across instances (within same process)
    _cache: ClassVar[list["CalendarEvent"]] = []
    _cache_time: ClassVar[datetime | None] = None

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=settings.scraper_timeout,
            headers={"User-Agent": settings.scraper_user_agent},
        )

    async def close(self):
        await self.client.aclose()

    def _is_cache_valid(self) -> bool:
        if not CalendarCollector._cache or CalendarCollector._cache_time is None:
            return False
        age = datetime.now(timezone.utc) - CalendarCollector._cache_time
        return age < CALENDAR_CACHE_TTL

    async def fetch_events(self, force_refresh: bool = False) -> list[CalendarEvent]:
        # Return cached data if valid and not forcing refresh
        if not force_refresh and self._is_cache_valid():
            logger.debug("Using cached calendar events", count=len(CalendarCollector._cache))
            return CalendarCollector._cache

        try:
            response = await self.client.get(FOREX_FACTORY_URL)
            response.raise_for_status()

            events_json = response.json()
            events = []

            for item in events_json:
                event = self._parse_event(item)
                if event:
                    events.append(event)

            # Update cache
            CalendarCollector._cache = events
            CalendarCollector._cache_time = datetime.now(timezone.utc)

            logger.info("Fetched and cached calendar events", count=len(events))
            return events

        except httpx.HTTPError as e:
            logger.error("HTTP error fetching calendar", error=str(e))
            # Return stale cache if available
            if CalendarCollector._cache:
                logger.warning("Returning stale cache due to fetch error")
                return CalendarCollector._cache
            return []
        except Exception as e:
            logger.error("Error fetching calendar", error=str(e))
            if CalendarCollector._cache:
                return CalendarCollector._cache
            return []
            return []

    def _parse_event(self, item: dict) -> CalendarEvent | None:
        try:
            title = item.get("title", "").strip()
            country = item.get("country", "").strip()
            impact = item.get("impact", "").strip()
            date_str = item.get("date", "")

            if not title or not date_str:
                return None

            try:
                date_utc = datetime.fromisoformat(date_str)
                if date_utc.tzinfo is None:
                    date_utc = date_utc.replace(tzinfo=timezone.utc)
                else:
                    date_utc = date_utc.astimezone(timezone.utc)
            except Exception:
                return None

            date_wib_obj = date_utc.astimezone(WIB)
            date_wib = date_wib_obj.strftime("%d/%m %H:%M WIB")

            currency_map = {
                "USD": "USD 🇺🇸",
                "EUR": "EUR 🇪🇺",
                "GBP": "GBP 🇬🇧",
                "JPY": "JPY 🇯🇵",
                "CHF": "CHF 🇨🇭",
                "AUD": "AUD 🇦🇺",
                "NZD": "NZD 🇳🇿",
                "CAD": "CAD 🇨🇦",
                "CNY": "CNY 🇨🇳",
            }
            currency = currency_map.get(country.upper(), country)

            event_id = f"{date_str}_{country}_{title[:30]}"

            return CalendarEvent(
                title=title,
                country=country,
                currency=currency,
                date_utc=date_utc,
                date_wib=date_wib,
                impact=impact,
                forecast=item.get("forecast", "").strip() or "—",
                previous=item.get("previous", "").strip() or "—",
                event_id=event_id,
            )

        except Exception as e:
            logger.warning("Error parsing calendar event", error=str(e))
            return None

    async def get_upcoming_high_impact(
        self,
        minutes_before: int = 15,
        minutes_window: int = 5,
    ) -> list[CalendarEvent]:
        events = await self.fetch_events()
        upcoming = []

        for event in events:
            if event.impact.lower() not in ("high", "red"):
                continue

            mins = event.minutes_until()
            
            min_bound = minutes_before - minutes_window
            max_bound = minutes_before
            
            if min_bound <= mins <= max_bound:
                upcoming.append(event)

        if upcoming:
            logger.info(
                "Found upcoming high-impact events",
                count=len(upcoming),
                events=[e.title for e in upcoming],
            )

        return upcoming
