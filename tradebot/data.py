"""Veri katmanı: CSV yükleme + borsa public API'den indirme.

CSV formatı: timestamp,open,high,low,close,volume
timestamp = UTC epoch ms veya ISO-8601.
"""
from __future__ import annotations

import time
from pathlib import Path

import pandas as pd

BINANCE_KLINES = "https://api.binance.com/api/v3/klines"
BYBIT_KLINES = "https://api.bybit.com/v5/market/kline"

_TF_MS = {"15m": 15 * 60_000, "1h": 3_600_000, "4h": 4 * 3_600_000, "1d": 86_400_000}


def load_csv(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.lower() for c in df.columns]
    ts = df["timestamp"]
    if pd.api.types.is_numeric_dtype(ts):
        idx = pd.to_datetime(ts, unit="ms", utc=True)
    else:
        idx = pd.to_datetime(ts, utc=True)
    df = df[["open", "high", "low", "close", "volume"]].astype(float)
    idx = pd.DatetimeIndex(idx)
    try:
        idx = idx.as_unit("ns")  # pandas sürümleri arası çözünürlük tutarlılığı
    except AttributeError:  # pandas < 2.0
        pass
    df.index = idx
    df = df[~df.index.duplicated(keep="first")].sort_index()
    return df


def download_binance(
    symbol: str, interval: str, start_ms: int, end_ms: int, pause: float = 0.35
) -> pd.DataFrame:
    """Binance public klines — API anahtarı gerekmez. Kendi makinende çalıştır."""
    import requests

    rows = []
    cursor = start_ms
    step = _TF_MS[interval] * 1000  # 1000 mum/istek
    while cursor < end_ms:
        resp = requests.get(
            BINANCE_KLINES,
            params={
                "symbol": symbol,
                "interval": interval,
                "startTime": cursor,
                "endTime": min(cursor + step - 1, end_ms),
                "limit": 1000,
            },
            timeout=30,
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            cursor += step
            continue
        rows.extend(batch)
        cursor = batch[-1][0] + _TF_MS[interval]
        time.sleep(pause)  # rate limit nezaketi

    df = pd.DataFrame(
        [[r[0], r[1], r[2], r[3], r[4], r[5]] for r in rows],
        columns=["timestamp", "open", "high", "low", "close", "volume"],
    )
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = df[c].astype(float)
    idx = pd.DatetimeIndex(pd.to_datetime(df["timestamp"], unit="ms", utc=True))
    try:
        idx = idx.as_unit("ns")
    except AttributeError:
        pass
    df.index = idx
    df = df.drop(columns=["timestamp"])
    df = df[~df.index.duplicated(keep="first")].sort_index()
    return df


def save_csv(df: pd.DataFrame, path: str | Path) -> None:
    out = df.copy()
    idx = pd.DatetimeIndex(out.index)
    # KRİTİK: yeni pandas sürümlerinde index ms/us çözünürlüklü olabilir;
    # view('int64') o durumda ns değil ms döner ve //10**6 tüm tarihleri
    # 1970'e çökertir (sessiz veri bozulması). Önce ns'e sabitle.
    try:
        idx = idx.as_unit("ns")
    except AttributeError:  # pandas < 2.0 zaten ns
        pass
    out.insert(0, "timestamp", (idx.view("int64") // 10**6))
    out.to_csv(path, index=False)


def validate_ohlcv(df: pd.DataFrame, interval: str) -> dict:
    """Veri kalite kontrolü: boşluk, sıra, mantık hataları."""
    problems = []
    if not df.index.is_monotonic_increasing:
        problems.append("index sıralı değil")
    bad = ((df["high"] < df["low"]) | (df["close"] > df["high"]) |
           (df["close"] < df["low"])).sum()
    if bad:
        problems.append(f"{bad} tutarsız OHLC satırı")
    expected = pd.Timedelta(milliseconds=_TF_MS[interval])
    gaps = (df.index.to_series().diff() > expected).sum()
    return {
        "rows": len(df),
        "start": str(df.index[0]) if len(df) else None,
        "end": str(df.index[-1]) if len(df) else None,
        "gaps": int(gaps),
        "problems": problems,
    }
