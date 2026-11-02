"""V3 — Seans kırılımı: sinyal ve emir kararı (docs/V3_SPEC_TASLAK.md §3, §4.1–4.3).

Bu modül YALNIZ veriden "niyet" (Intent) üretir; boyut, dolum ve çıkışlar
tradebot/engine_v3.py'dedir. Parametreler spesifikasyonda sabittir; optimize edilmez.

Girdi: 15m OHLC DataFrame, index = mum açılış zamanı (int, UTC epoch ms, 15 dk'nın katı).
Her niyet yalnız tetik mumu t'nin kapanışında ve öncesinde bilinen veriyle üretilir.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

BAR_MS = 900_000
DAY_MS = 86_400_000
BARS_PER_DAY = 96
ASIA_SLOTS = range(0, 28)          # 00:00–06:45 açılışlı
TRIGGER_SLOTS = range(28, 80)      # 07:00–19:45 açılışlı
LAST_SLOT = 95                     # 23:45 açılışlı
MIN_VALID_BARS = 90                # günlük kapanış geçerliliği (§3)
SMA_N = 20                         # §3
MIN_STOP = 0.01                    # §4.3
RR = 2.0                           # §4.7


@dataclass(frozen=True)
class Intent:
    symbol: str
    day: int          # UTC gün indeksi
    side: str         # "long" | "short"
    trigger_ts: int   # t mumunun açılış zamanı (ms)
    P: float          # t kapanışı (referans)
    M: float          # Asya orta noktası (stop)


@dataclass
class DayInfo:
    """Günlük kayıt: neden işlem olmadığı dahil (fizibilite raporu için)."""
    day: int
    status: str       # "intent" | "no_asia" | "no_trend" | "flat_trend" | "no_trigger" | "wrong_side" | "min_stop"


def _validate(df: pd.DataFrame) -> None:
    idx = df.index
    if not idx.is_monotonic_increasing or idx.has_duplicates:
        raise ValueError("zaman indeksi sıralı/tekil değil")
    if (np.asarray(idx, dtype="int64") % BAR_MS != 0).any():
        raise ValueError("15 dakikaya hizalı olmayan mum")


def daily_closes(df: pd.DataFrame) -> dict:
    """{gün: C_d} yalnız geçerli günler için (≥ 90 mum VE 23:45 mumu mevcut)."""
    ts = np.asarray(df.index, dtype="int64")
    day = ts // DAY_MS
    slot = (ts % DAY_MS) // BAR_MS
    close = df["close"].to_numpy(dtype=float)
    out = {}
    counts = pd.Series(1, index=day).groupby(level=0).sum()
    last = {int(d): float(c) for d, s, c in zip(day, slot, close) if s == LAST_SLOT}
    for d, n in counts.items():
        if n >= MIN_VALID_BARS and int(d) in last:
            out[int(d)] = last[int(d)]
    return out


def trend_side(closes: dict, d: int) -> str | None:
    """§3: referans gün d−1 geçerli olmalı; SMA = d−1 dahil son 20 geçerli kapanış."""
    if (d - 1) not in closes:
        return None
    valid = [k for k in closes if k <= d - 1]
    if len(valid) < SMA_N:
        return None
    last20 = sorted(valid)[-SMA_N:]
    sma = sum(closes[k] for k in last20) / SMA_N
    c = closes[d - 1]
    if c > sma:
        return "long"
    if c < sma:
        return "short"
    return "flat"


def generate_intents(symbol: str, df: pd.DataFrame, start_day: int, end_day: int,
                     log: list | None = None) -> list:
    """start_day..end_day (dahil) günleri için niyetler. Önceki veri yalnız ısınma."""
    _validate(df)
    closes = daily_closes(df)
    ts = np.asarray(df.index, dtype="int64")
    o, h, l, c = (df[k].to_numpy(dtype=float) for k in ("open", "high", "low", "close"))
    day_arr = ts // DAY_MS
    intents = []
    # gün → satır aralığı
    bounds = {}
    for i, d in enumerate(day_arr):
        d = int(d)
        if d not in bounds:
            bounds[d] = [i, i]
        bounds[d][1] = i
    valid_sorted = sorted(closes)
    for d in range(start_day, end_day + 1):
        def note(st):
            if log is not None:
                log.append(DayInfo(d, st))
        if d not in bounds:
            note("no_asia")
            continue
        a, b = bounds[d]
        slots = (ts[a:b + 1] % DAY_MS) // BAR_MS
        rows = {int(s): a + k for k, s in enumerate(slots)}
        if any(s not in rows for s in ASIA_SLOTS):
            note("no_asia")
            continue
        ah = max(h[rows[s]] for s in ASIA_SLOTS)
        al = min(l[rows[s]] for s in ASIA_SLOTS)
        M = (ah + al) / 2.0
        # trend: d−1 dahil son 20 geçerli kapanış (ikili arama ile hızlı)
        if (d - 1) not in closes:
            note("no_trend")
            continue
        k = np.searchsorted(valid_sorted, d - 1, side="right")
        if k < SMA_N:
            note("no_trend")
            continue
        sma = sum(closes[x] for x in valid_sorted[k - SMA_N:k]) / SMA_N
        cref = closes[d - 1]
        side = "long" if cref > sma else ("short" if cref < sma else None)
        if side is None:
            note("flat_trend")
            continue
        trig = None
        for s in TRIGGER_SLOTS:
            if s not in rows:
                continue
            r = rows[s]
            if (side == "long" and c[r] > ah) or (side == "short" and c[r] < al):
                trig = r
                break
        if trig is None:
            note("no_trigger")
            continue
        P = float(c[trig])
        if (side == "long" and P <= M) or (side == "short" and P >= M):
            note("wrong_side")
            continue
        if abs(P - M) / P < MIN_STOP:
            note("min_stop")
            continue
        intents.append(Intent(symbol, d, side, int(ts[trig]), P, M))
        note("intent")
    return intents
