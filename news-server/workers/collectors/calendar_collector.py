"""
Calendar Event Collector for Forex Factory

Fetches high-impact economic events from Forex Factory API.
"""
import httpx
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from app.core.logging import get_logger
from app.core.config import settings


logger = get_logger(__name__)

# Forex Factory free API
FOREX_FACTORY_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

# WIB timezone (UTC+7)
WIB = ZoneInfo("Asia/Jakarta")


@dataclass
class CalendarEvent:
    title: str
    country: str
    currency: str
    date_utc: datetime
    date_wib: str  # Formatted WIB time string
    impact: str
    forecast: str
    previous: str
    event_id: str  # For deduplication

    def minutes_until(self) -> int:
        """Minutes until this event starts."""
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

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=settings.scraper_timeout,
            headers={"User-Agent": settings.scraper_user_agent},
        )

    async def close(self):
        await self.client.aclose()

    async def fetch_events(self) -> list[CalendarEvent]:
        """Fetch all events from Forex Factory."""
        try:
            response = await self.client.get(FOREX_FACTORY_URL)
            response.raise_for_status()

            events_json = response.json()
            events = []

            for item in events_json:
                event = self._parse_event(item)
                if event:
                    events.append(event)

            logger.info("Fetched calendar events", count=len(events))
            return events

        except httpx.HTTPError as e:
            logger.error("HTTP error fetching calendar", error=str(e))
            return []
        except Exception as e:
            logger.error("Error fetching calendar", error=str(e))
            return []

    def _parse_event(self, item: dict) -> CalendarEvent | None:
        """Parse a single event from JSON."""
        try:
            title = item.get("title", "").strip()
            country = item.get("country", "").strip()
            impact = item.get("impact", "").strip()
            date_str = item.get("date", "")

            if not title or not date_str:
                return None

            # Parse date - format: "2026-02-07T13:30:00-05:00"
            try:
                date_utc = datetime.fromisoformat(date_str)
                if date_utc.tzinfo is None:
                    date_utc = date_utc.replace(tzinfo=timezone.utc)
                else:
                    date_utc = date_utc.astimezone(timezone.utc)
            except Exception:
                return None

            # Convert to WIB
            date_wib_obj = date_utc.astimezone(WIB)
            date_wib = date_wib_obj.strftime("%d/%m %H:%M WIB")

            # Currency mapping
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

            # Generate event ID for deduplication
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
        """
        Get high-impact events starting within the specified time window.
        
        Args:
            minutes_before: Alert X minutes before event (default: 15)
            minutes_window: Window size in minutes (default: 5)
            
        Returns:
            List of events starting between (minutes_before - minutes_window) 
            and minutes_before from now.
            
        Example:
            minutes_before=15, minutes_window=5
            Returns events starting in 10-15 minutes.
        """
        events = await self.fetch_events()
        upcoming = []

        for event in events:
            # Filter high impact only
            if event.impact.lower() not in ("high", "red"):
                continue

            mins = event.minutes_until()
            
            # Check if within window
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
