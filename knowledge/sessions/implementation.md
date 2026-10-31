# Sessions — Implementation

> NOT: Üretim kodu `tradebot/sessions.py` içindedir. Buradaki kod referanstır.

## Python: Session Filter

```python
from datetime import datetime, time
import pytz
from enum import Enum

class Session(Enum):
    ASIAN = "asian"
    LONDON = "london"
    NEW_YORK = "new_york"
    OVERLAP = "london_ny_overlap"
    OFF = "off_hours"

# Killzone saatleri (UTC)
KILLZONES = {
    Session.LONDON: (time(7, 0), time(9, 0)),
    Session.NEW_YORK: (time(13, 0), time(15, 0)),
}

# Tüm seans saatleri (UTC)
SESSION_HOURS = {
    Session.ASIAN: (time(0, 0), time(9, 0)),
    Session.LONDON: (time(7, 0), time(16, 0)),
    Session.NEW_YORK: (time(13, 0), time(22, 0)),
    Session.OVERLAP: (time(13, 0), time(16, 0)),
}

def get_current_session(dt: datetime = None) -> Session:
    """Şu anki seans/killzone'u döner."""
    if dt is None:
        dt = datetime.now(pytz.UTC)
    elif dt.tzinfo is None:
        dt = pytz.UTC.localize(dt)

    current_time = dt.time()

    # Öncelik sırası ÖNEMLİ: Overlap > London > NY > Asian.
    # (Eski sürüm dict sırasıyla geziyordu → 07:00-09:00 arası,
    # Asian 00:00-09:00 ile örtüştüğü için London KZ saatinde
    # "asian" dönüyordu — session filtresi yanlış çalışırdı.)
    PRIORITY = [Session.OVERLAP, Session.LONDON, Session.NEW_YORK, Session.ASIAN]
    for session in PRIORITY:
        lo, hi = SESSION_HOURS[session]
        if lo <= current_time < hi:
            return session

    return Session.OFF

def is_killzone(dt: datetime = None) -> bool:
    """Şu an bir killzone süreci mi?"""
    if dt is None:
        dt = datetime.now(pytz.UTC)
    elif dt.tzinfo is None:
        dt = pytz.UTC.localize(dt)

    current_time = dt.time()

    for session, (lo, hi) in KILLZONES.items():
        if lo <= current_time < hi:
            return True

    return False

def can_enter_trade(dt: datetime = None) -> tuple[bool, str]:
    """Session filtresi: sadece KZ'de entry izni ver."""
    if is_killzone(dt):
        session = get_current_session(dt)
        return True, f"Killzone aktif: {session.value}"
    return False, "Killzone dışı, entry bekleniyor"
```

---

## Pine Script: Session Overlay

```pine
//@version=5
indicator("Session Boxes", overlay=true)

// KRİTİK: time() session string'i varsayılan olarak BORSANIN saat diliminde
// yorumlanır. UTC sabitlemek için üçüncü parametre "UTC" ZORUNLU —
// aksi halde killzone kutuları borsaya göre kayar (eski hata).

// London KZ: 07:00-09:00 UTC
londonKZStart = time(timeframe.period, "0700-0900", "UTC")
// NY KZ: 13:00-15:00 UTC
nyKZStart = time(timeframe.period, "1300-1500", "UTC")

// Asian range: 00:00-07:00 UTC
asianSession = time(timeframe.period, "0000-0700", "UTC")

bgcolor(not na(londonKZStart) ? color.new(color.blue, 90) : na,
    title="London KZ")
bgcolor(not na(nyKZStart) ? color.new(color.orange, 90) : na,
    title="NY KZ")
bgcolor(not na(asianSession) ? color.new(color.gray, 95) : na,
    title="Asian")
```

---

## Webhook Session Ekleme

```python
def build_webhook_payload(signal: dict) -> dict:
    """Webhook payload'una seans bilgisi ekler."""
    session = get_current_session()
    in_kz = is_killzone()

    return {
        **signal,
        "session": session.value,
        "in_killzone": in_kz,
        "timestamp_utc": datetime.now(pytz.UTC).isoformat(),
    }
```
