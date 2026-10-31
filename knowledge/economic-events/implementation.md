# Economic Events — Implementation

## Python: Economic Calendar Servisi

```python
import httpx
import asyncio
from datetime import datetime, date, timedelta
from dataclasses import dataclass
import pytz

@dataclass
class EconomicEvent:
    title: str
    impact: str        # "high", "medium", "low"
    time_utc: datetime
    currency: str      # "USD", "EUR" vb.
    actual: str = None
    forecast: str = None
    previous: str = None

HIGH_IMPACT_KEYWORDS = [
    "FOMC", "Federal Reserve", "Fed Rate",
    "Non-Farm", "NFP",
    "CPI", "Consumer Price",
    "PCE",
    "GDP",
    "Unemployment Rate",
    "Powell",
    "Yellen",
]

class EconomicCalendar:
    """ForexFactory'den haber takvimi çeker."""

    BASE_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

    async def fetch_events(self) -> list[EconomicEvent]:
        """Bu haftanın haberlerini çeker."""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(self.BASE_URL)
            resp.raise_for_status()
            data = resp.json()

        events = []
        for item in data:
            if item.get('impact') != 'High':
                continue
            if item.get('country') != 'USD':
                continue

            # Zaman parse — KRİTİK: ff_calendar JSON'unda 'date' alanı
            # ISO-8601 formatında ve KENDİ offset'iyle gelir
            # (örn. "2026-07-06T08:30:00-04:00" = US Eastern).
            # Eski sürüm saati doğrudan UTC varsayıyordu → haber penceresi
            # 4-5 saat kayardı; FOMC/NFP saatinde sistem AÇIK kalırdı!
            try:
                event_time = datetime.fromisoformat(item['date'])
                event_time = event_time.astimezone(pytz.UTC)
            except (ValueError, KeyError):
                continue

            events.append(EconomicEvent(
                title=item.get('title', ''),
                impact='high',
                time_utc=event_time,
                currency='USD',
                forecast=item.get('forecast'),
                previous=item.get('previous'),
            ))

        return events

    def is_news_window(
        self,
        events: list[EconomicEvent],
        dt: datetime = None,
        pre_minutes: int = 30,
        post_minutes: int = 15,
    ) -> tuple[bool, str]:
        """
        Şu an bir high-impact haber penceresinde mi?
        Haber öncesi 30dk + sonrası 15dk bloke.
        """
        if dt is None:
            dt = datetime.now(pytz.UTC)
        elif dt.tzinfo is None:
            dt = pytz.UTC.localize(dt)

        for event in events:
            window_start = event.time_utc - timedelta(minutes=pre_minutes)
            window_end = event.time_utc + timedelta(minutes=post_minutes)
            if window_start <= dt <= window_end:
                return True, f"Haber penceresi: {event.title} @ {event.time_utc}"

        return False, "OK"
```

---

## Risk Engine Entegrasyonu

```python
class EnhancedRiskEngine(RiskEngine):
    def __init__(self, config, account_balance, calendar: EconomicCalendar):
        super().__init__(config, account_balance)
        self.calendar = calendar
        self._cached_events: list[EconomicEvent] = []
        self._last_fetch: datetime = None

    async def refresh_events(self):
        now = datetime.now(pytz.UTC)
        # Saatte bir güncelle.
        # NOT: timedelta.seconds DEĞİL total_seconds() kullanılır —
        # .seconds gün bileşenini atar (25 saat → 3600s görünür, hata).
        if self._last_fetch is None or (now - self._last_fetch).total_seconds() > 3600:
            self._cached_events = await self.calendar.fetch_events()
            self._last_fetch = now

    def can_trade(self) -> tuple[bool, str]:
        # Üst sınıf kontrolü
        ok, msg = super().can_trade()
        if not ok:
            return ok, msg

        # Haber penceresi kontrolü
        in_news, news_msg = self.calendar.is_news_window(self._cached_events)
        if in_news:
            return False, news_msg

        return True, "OK"
```

---

## Webhook Payload'una Haber Bilgisi

```python
def enrich_signal_with_news(signal: dict, events: list[EconomicEvent]) -> dict:
    """Sinyal payload'una yakın haber var mı bilgisi ekler."""
    now = datetime.now(pytz.UTC)
    upcoming = [
        e for e in events
        if timedelta(0) < (e.time_utc - now) < timedelta(hours=4)
    ]

    return {
        **signal,
        "news_warning": len(upcoming) > 0,
        "upcoming_events": [e.title for e in upcoming],
    }
```
