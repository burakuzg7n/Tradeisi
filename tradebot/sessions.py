"""Seans / killzone filtresi. Tüm sistem UTC çalışır."""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

# (start_hour, end_hour) UTC, [start, end)
LONDON_KZ = (7, 10)
NY_KZ = (13, 16)

SESSION_NAMES = [
    ((13, 16), "london_ny_overlap"),
    ((7, 16), "london"),
    ((13, 22), "new_york"),
    ((0, 9), "asian"),
]


def session_name(ts: datetime | pd.Timestamp) -> str:
    """Öncelik: overlap > london > new_york > asian."""
    h = ts.hour
    for (lo, hi), name in SESSION_NAMES:
        if lo <= h < hi:
            return name
    return "off_hours"


def in_killzone(ts: datetime | pd.Timestamp, killzones=(LONDON_KZ, NY_KZ)) -> bool:
    h = ts.hour
    return any(lo <= h < hi for lo, hi in killzones)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
