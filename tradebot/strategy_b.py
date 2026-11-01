"""Plan B sinyalleri: Donchian 55/20 + Wilder ATR(20), günlük, yalnız long.

Kurallar: DEVIR_NOTU §9 + docs/SPEC_EKLERI.md E5, E5b, E6.
Bu modül yalnız SÜTUN üretir (entry_signal, exit_signal, atr); yürütme
tradebot/portfolio_b.py'dedir. Parametreler §9'da sabittir, optimize edilmez.

Tanımlar (bar = mevcut günlük bar; eksik gün satır olarak YOKTUR, E5/E5b):
- Giriş kanalı(t) = önceki 55 mevcut barın en yüksek HIGH'ı (t hariç).
- Çıkış kanalı(t) = önceki 20 mevcut barın en düşük LOW'u (t hariç).
- entry_signal(t) = close(t) > giriş kanalı(t)  (eşitlik sinyal değildir).
  Önceki 55 bar yoksa veya ATR(t) hazır değilse False (E5: yeterli geçmiş şartı).
- exit_signal(t) = close(t) < çıkış kanalı(t). Önceki 20 bar yoksa False.
- True range(t) = max(high−low, |high−close_önceki|, |low−close_önceki|);
  close_önceki = bir önceki MEVCUT barın kapanışı. İlk barın TR'si yoktur.
- ATR (E6, Wilder): ilk değer = ilk 20 TR'nin (2.–21. bar) basit ortalaması,
  sonrası ATR(t) = (ATR(t−1)·19 + TR(t)) / 20. ATR(t), t gününün kapanışında bilinir.
Her değer yalnız t ve öncesindeki barlarla hesaplanır (lookahead yok; testlerle denetlenir).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ENTRY_LOOKBACK = 55   # §9
EXIT_LOOKBACK = 20    # §9
ATR_PERIOD = 20       # §9 / E6
DAY_MS = 86_400_000


def wilder_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray,
               n: int = ATR_PERIOD) -> np.ndarray:
    m = len(close)
    atr = np.full(m, np.nan)
    if m < n + 1:
        return atr
    prev_c = close[:-1]
    h, l = high[1:], low[1:]
    tr = np.maximum.reduce([h - l, np.abs(h - prev_c), np.abs(l - prev_c)])  # tr[k] = bar k+1
    atr[n] = tr[:n].mean()
    for i in range(n + 1, m):
        atr[i] = (atr[i - 1] * (n - 1) + tr[i - 1]) / n
    return atr


def compute_signals(df: pd.DataFrame) -> pd.DataFrame:
    """df: index = UTC gün indeksi (int, sıralı, tekil), sütunlar open/high/low/close.
    Dönüş: aynı index + entry_signal, exit_signal, atr, entry_channel, exit_channel."""
    if not df.index.is_monotonic_increasing or df.index.has_duplicates:
        raise ValueError("gün indeksi sıralı/tekil değil")
    out = df[["open", "high", "low", "close"]].astype(float).copy()
    high, low, close = out["high"], out["low"], out["close"]
    entry_ch = high.shift(1).rolling(ENTRY_LOOKBACK, min_periods=ENTRY_LOOKBACK).max()
    exit_ch = low.shift(1).rolling(EXIT_LOOKBACK, min_periods=EXIT_LOOKBACK).min()
    atr = pd.Series(wilder_atr(high.to_numpy(), low.to_numpy(), close.to_numpy()),
                    index=out.index)
    out["entry_channel"] = entry_ch
    out["exit_channel"] = exit_ch
    out["atr"] = atr
    out["entry_signal"] = (close > entry_ch) & entry_ch.notna() & atr.notna()
    out["exit_signal"] = (close < exit_ch) & exit_ch.notna()
    return out


def load_daily(path: str | Path) -> pd.DataFrame:
    """data/{SEMBOL}_1d.csv → gün indeksli OHLC. Hizasız/tekrar satırda hata (E14 zaten engeller)."""
    raw = pd.read_csv(path)
    ts = raw["timestamp"].astype("int64")
    if (ts % DAY_MS != 0).any():
        raise ValueError(f"{Path(path).name}: 00:00 UTC'ye hizalı olmayan mum")
    df = raw[["open", "high", "low", "close"]].astype(float)
    df.index = pd.Index((ts // DAY_MS).to_numpy(), name="day")
    if not df.index.is_monotonic_increasing or df.index.has_duplicates:
        raise ValueError(f"{Path(path).name}: gün indeksi sıralı/tekil değil")
    return df


def build_frames(data_dir: str | Path, symbols) -> dict:
    """Motor girdisi: {sembol: compute_signals(load_daily(...))}."""
    data_dir = Path(data_dir)
    return {s: compute_signals(load_daily(data_dir / f"{s}_1d.csv")) for s in symbols}
