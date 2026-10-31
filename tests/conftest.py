import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
import pytest


def make_df(bars: list[tuple], start="2026-01-01", freq="15min") -> pd.DataFrame:
    """bars: [(open, high, low, close), ...] → OHLCV DataFrame (UTC)."""
    idx = pd.date_range(start, periods=len(bars), freq=freq, tz="UTC")
    df = pd.DataFrame(bars, columns=["open", "high", "low", "close"], dtype=float)
    df["volume"] = 100.0
    df.index = idx
    return df


@pytest.fixture
def flat_df():
    return make_df([(100, 101, 99, 100)] * 60)


def synthetic_trend_df(n=2000, seed=7, freq="15min") -> pd.DataFrame:
    """Rejim değiştiren sentetik seri — motor doğrulaması için."""
    rng = np.random.default_rng(seed)
    drift = np.where((np.arange(n) // 400) % 2 == 0, 0.0004, -0.0004)
    rets = rng.normal(drift, 0.004)
    close = 50000 * np.exp(np.cumsum(rets))
    high = close * (1 + np.abs(rng.normal(0, 0.002, n)))
    low = close * (1 - np.abs(rng.normal(0, 0.002, n)))
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    high = np.maximum.reduce([high, open_, close])
    low = np.minimum.reduce([low, open_, close])
    idx = pd.date_range("2025-01-01", periods=n, freq=freq, tz="UTC")
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": 100.0},
        index=idx,
    )
