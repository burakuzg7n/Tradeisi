"""Yeni motor (`trader/`) icin ortak test yardimcilari."""
from __future__ import annotations

import pandas as pd
import pytest


def make_ohlcv(rows, start: str = "2023-01-01", freq: str = "15min") -> pd.DataFrame:
    """rows: (open, high, low, close, volume) listesi -> UTC indexli OHLCV."""
    idx = pd.date_range(start, periods=len(rows), freq=freq, tz="UTC")
    df = pd.DataFrame(list(rows), columns=["open", "high", "low", "close", "volume"])
    df.index = idx
    return df.astype(float)


def flat_ohlcv(n: int, price: float = 100.0, start: str = "2023-01-01",
               freq: str = "15min", volume: float = 1000.0) -> pd.DataFrame:
    rows = [(price, price, price, price, volume) for _ in range(n)]
    return make_ohlcv(rows, start=start, freq=freq)


class OneShot:
    """Tek bir bard sinyal ureten minimal strateji (test icin)."""

    name = "test_one_shot"
    research_candidate = False
    timeframe = "15m"

    def __init__(self, index: int = 0, side: str = "long", entry: float | None = None,
                 stop_pct: float = 0.05, target_pct: float = 0.10,
                 weight: float | None = None):
        self.index = index
        self.side = side
        self.entry = entry
        self.stop_pct = stop_pct
        self.target_pct = target_pct
        self.weight = weight
        self.seen_max_ts = None
        self.calls = 0

    def generate(self, panel, ts):
        from trader.strategy import Signal

        self.calls += 1
        # stratejiye gecmisin disina tasma olup olmadigini olc
        for sym in panel.symbols():
            df = panel.frame(sym)
            if len(df):
                self.seen_max_ts = df.index[-1]
        if panel.last_ts() is None:
            return []
        if len(panel.frame(list(panel.symbols())[0])) - 1 != self.index:
            return []
        close = float(panel.frame(list(panel.symbols())[0])["close"].iloc[-1])
        entry = self.entry if self.entry is not None else close
        if self.weight is not None:
            return [Signal(symbol=list(panel.symbols())[0], side=self.side,
                           action="target_weight", weight=self.weight,
                           ts=ts.isoformat(), meta={})]
        if self.side == "long":
            stop = entry * (1 - self.stop_pct)
            target = entry * (1 + self.target_pct)
        else:
            stop = entry * (1 + self.stop_pct)
            target = entry * (1 - self.target_pct)
        return [Signal(symbol=list(panel.symbols())[0], side=self.side, action="open",
                       entry=entry, stop=stop, target=target,
                       ts=ts.isoformat(), meta={})]


@pytest.fixture
def tmp_store(tmp_path):
    from trader.store import Store

    store = Store(str(tmp_path / "test.db"))
    yield store
    store.close()
