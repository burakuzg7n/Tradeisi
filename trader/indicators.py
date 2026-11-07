"""Teknik indikatorler — hepsi SADECE gecmis veriye bakar (lookahead yok).

Kural: bir bar icin hesaplanan deger o barin KAPANISINDA hesaplanabilir.
Gelecege bakan bir islem burada yapilmaz; `shift(1)` gerektiren yerler
acikca belirtilir.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def log_returns(close: pd.Series) -> pd.Series:
    """Log getiriler (sadece kapanislar arasinda)."""
    return np.log(close / close.shift(1))


def pct_returns(close: pd.Series) -> pd.Series:
    return close.pct_change()


def sma(s: pd.Series, window: int) -> pd.Series:
    return s.rolling(window, min_periods=window).mean()


def ema(s: pd.Series, span: int) -> pd.Series:
    return s.ewm(span=span, adjust=False).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder RSI. `min_periods=period` — ilk `period-1` bar NaN'dir."""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    # Wilder yumusatma: alpha = 1/period
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100.0 - (100.0 / (1.0 + rs))
    # avg_loss == 0 ise RSI = 100 (tum kazanclar, hic zarar yok)
    out = out.where(avg_loss.notna() & (avg_loss != 0.0), other=np.nan)
    out = out.where(~((avg_loss == 0.0) & avg_gain.notna()), other=100.0)
    return out


def true_range(df: pd.DataFrame) -> pd.Series:
    """TR = max(H-L, |H-prevC|, |L-prevC|)."""
    prev_close = df["close"].shift(1)
    return pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Wilder ATR."""
    tr = true_range(df)
    return tr.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()


def realized_vol(returns: pd.Series, window: int, periods_per_year: int) -> pd.Series:
    """Yilliklandirilmis gerceklesmis oynaklik (rolling std)."""
    return returns.rolling(window, min_periods=window).std(ddof=1) * np.sqrt(periods_per_year)


def momentum(close: pd.Series, lookback: int, skip: int = 0) -> pd.Series:
    """Momentum: close[t-skip] / close[t-skip-lookback] - 1.

    `skip` gunluk momentumun en son gunlerdeki tersine donus etkisini
    (1 haftalik reversal) azaltmak icin kullanilir. Bugunun `skip` gunu
    HARIC fiyatini kullanir — yani bugunku kapanis bilgiye dahil DEGILDIR.
    """
    if skip:
        base = close.shift(skip)
    else:
        base = close
    return base / base.shift(lookback) - 1.0


def zscore(s: pd.Series, window: int) -> pd.Series:
    ma = s.rolling(window, min_periods=window).mean()
    sd = s.rolling(window, min_periods=window).std(ddof=1)
    return (s - ma) / sd.replace(0.0, np.nan)


def cross_above(a: pd.Series, b: pd.Series) -> pd.Series:
    return (a > b) & (a.shift(1) <= b.shift(1))


def cross_below(a: pd.Series, b: pd.Series) -> pd.Series:
    return (a < b) & (a.shift(1) >= b.shift(1))
