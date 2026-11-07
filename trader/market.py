"""Borsa veri katmani: OHLCV + funding (perpetual) indirme, onbellek, dogrulama.

Kaynaklar:
    Binance USDT-M futures : https://fapi.binance.com  (public, anahtar gerekmez)
    Bybit   linear          : https://api.bybit.com      (public, anahtar gerekmez)

Onbellek `data/` altinda CSV olarak tutulur; ayni dosya varsa yeniden
indirilmez (rekor tutarliligi icin). Indirme sonrasi dogrulama (veri
sagligi) raporu uretilir.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from .config import DATA_DIR, ROOT

BINANCE_FAPI = "https://fapi.binance.com"
BYBIT_V5 = "https://api.bybit.com"

TF_MS = {
    "1m": 60_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h": 3_600_000,
    "4h": 14_400_000,
    "1d": 86_400_000,
}

# Gunluk barda yil basina bar sayisi (365)
PERIODS_PER_YEAR = {"1m": 365 * 1440, "5m": 365 * 288, "15m": 365 * 96,
                    "30m": 365 * 48, "1h": 365 * 24, "4h": 365 * 6, "1d": 365}


class MarketError(RuntimeError):
    pass


# --------------------------------------------------------------------------
# indirme
# --------------------------------------------------------------------------

def _http_json(url: str, params: dict, timeout: int = 30) -> object:
    import requests

    resp = requests.get(url, params=params, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def download_binance_ohlcv(
    symbol: str, interval: str, start_ms: int, end_ms: int, pause: float = 0.25
) -> pd.DataFrame:
    """Binance USDT-M perpetual mumlar. API anahtari gerekmez."""
    import requests

    rows: list = []
    cursor = start_ms
    step = TF_MS[interval] * 1000  # 1000 mum/istek
    while cursor < end_ms:
        resp = requests.get(
            f"{BINANCE_FAPI}/fapi/v1/klines",
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
        cursor = int(batch[-1][0]) + TF_MS[interval]
        time.sleep(pause)

    if not rows:
        return _empty_ohlcv()
    df = pd.DataFrame(
        [[r[0], r[1], r[2], r[3], r[4], r[5]] for r in rows],
        columns=["timestamp", "open", "high", "low", "close", "volume"],
    )
    return _finalize(df)


def download_bybit_ohlcv(
    symbol: str, interval: str, start_ms: int, end_ms: int, pause: float = 0.25
) -> pd.DataFrame:
    """Bybit linear mumlar. `symbol` = 'BTCUSDT'."""
    rows: list = []
    cursor = start_ms
    step = TF_MS[interval] * 1000
    bybit_tf = {"1m": "1", "5m": "5", "15m": "15", "30m": "30",
                "1h": "60", "4h": "240", "1d": "D"}[interval]
    while cursor < end_ms:
        payload = _http_json(
            f"{BYBIT_V5}/v5/market/kline",
            {
                "category": "linear",
                "symbol": symbol,
                "interval": bybit_tf,
                "start": cursor,
                "end": min(cursor + step - 1, end_ms),
                "limit": 1000,
            },
        )
        batch = payload.get("result", {}).get("list", [])
        if not batch:
            cursor += step
            continue
        # Bybit listesi [startTime, open, high, low, close, volume, turnover] — ters sirali
        for item in reversed(batch):
            rows.append([int(item[0]), item[1], item[2], item[3], item[4], item[5]])
        cursor = int(batch[0][0]) + TF_MS[interval]
        time.sleep(pause)

    if not rows:
        return _empty_ohlcv()
    df = pd.DataFrame(
        [[r[0], r[1], r[2], r[3], r[4], r[5]] for r in rows],
        columns=["timestamp", "open", "high", "low", "close", "volume"],
    )
    return _finalize(df)


FUNDING_WINDOW_MS = 300 * 86_400_000  # tek istekte en fazla 1000 kayit (~333 gun)


def download_binance_funding(symbol: str, start_ms: int, end_ms: int,
                             pause: float = 0.25) -> pd.DataFrame:
    """Perpetual funding oranlari (gercek). Sonuc: timestamp + funding_rate.

    Binance `fundingRate` en fazla 1000 kayit dondurur (8 saatlik funding ->
    ~333 gun). 300 gunluk pencereler kullanilir; bir pencerede 900 kayittan
    fazla olmadigi icin API limiti dolmaz ve tum kayitlar tek seferde gelir.

    Sayfalama kurali:
      * API 1000 kayit dondurduyse pencerede daha fazla kayit olabilir ->
        son kaydin bir milisaniye sonrasindan devam et.
      * API 1000'den az kayit dondurduyse pencere tamamen alinmistir ->
        bir sonraki pencereye atla (ilerleme garantisi).
    """
    import requests

    rows: list = []
    cursor = start_ms
    while cursor < end_ms:
        window_end = min(cursor + FUNDING_WINDOW_MS - 1, end_ms)
        resp = requests.get(
            f"{BINANCE_FAPI}/fapi/v1/fundingRate",
            params={"symbol": symbol, "startTime": cursor,
                    "endTime": window_end, "limit": 1000},
            timeout=30,
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            cursor = window_end + 1
            time.sleep(pause)
            continue
        rows.extend(batch)
        if len(batch) >= 1000:
            last = int(batch[-1]["fundingTime"])
            cursor = max(last + 1, cursor + 1)
        else:
            cursor = window_end + 1
        time.sleep(pause)
    if not rows:
        return pd.DataFrame(columns=["funding_rate"],
                            index=pd.DatetimeIndex([], tz="UTC"))
    df = pd.DataFrame(
        [[int(r["fundingTime"]), float(r["fundingRate"])] for r in rows],
        columns=["timestamp", "funding_rate"],
    )
    df = df[df["timestamp"] <= end_ms]
    return finalize_funding(df)


def _empty_ohlcv() -> pd.DataFrame:
    df = pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
    return _finalize(df)


def _finalize(df: pd.DataFrame) -> pd.DataFrame:
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = df[col].astype(float)
    idx = pd.DatetimeIndex(pd.to_datetime(df["timestamp"], unit="ms", utc=True))
    try:
        idx = idx.as_unit("ns")
    except AttributeError:  # pandas < 2.0
        pass
    df.index = idx
    df = df.drop(columns=["timestamp"])
    df = df[~df.index.duplicated(keep="first")].sort_index()
    return df


def finalize_funding(df: pd.DataFrame) -> pd.DataFrame:
    """Funding tablosunu zaman damgali index'e cevirir."""
    if len(df) == 0:
        df = df.copy()
        df.index = pd.DatetimeIndex([], tz="UTC")
        try:
            df.index = df.index.as_unit("ns")
        except AttributeError:
            pass
        return df
    df = df.copy()
    df["funding_rate"] = df["funding_rate"].astype(float)
    idx = pd.DatetimeIndex(pd.to_datetime(df["timestamp"], unit="ms", utc=True))
    try:
        idx = idx.as_unit("ns")
    except AttributeError:  # pandas < 2.0
        pass
    df.index = idx
    df = df.drop(columns=["timestamp"])
    df = df[~df.index.duplicated(keep="first")].sort_index()
    return df


# --------------------------------------------------------------------------
# onbellek
# --------------------------------------------------------------------------

def cache_path(exchange: str, symbol: str, interval: str, kind: str = "ohlcv") -> Path:
    safe = symbol.replace("/", "_").replace(":", "_")
    return DATA_DIR / f"{exchange}_{kind}_{safe}_{interval}.csv"


def save_csv(df: pd.DataFrame, path: Path) -> None:
    out = df.copy()
    idx = pd.DatetimeIndex(out.index)
    try:
        idx = idx.as_unit("ns")
    except AttributeError:
        pass
    out.insert(0, "timestamp", (idx.view("int64") // 10**6))
    out.to_csv(path, index=False)


def load_csv(path: Path) -> pd.DataFrame:
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
        idx = idx.as_unit("ns")
    except AttributeError:
        pass
    df.index = idx
    df = df[~df.index.duplicated(keep="first")].sort_index()
    return df


def save_funding_csv(df: pd.DataFrame, path: Path) -> None:
    """Funding tablosunu CSV olarak yazar (timestamp + funding_rate)."""
    out = df.copy()
    idx = pd.DatetimeIndex(out.index)
    try:
        idx = idx.as_unit("ns")
    except AttributeError:
        pass
    out.insert(0, "timestamp", (idx.view("int64") // 10**6))
    out.to_csv(path, index=False)


def load_funding_csv(path: Path) -> pd.DataFrame:
    """Funding CSV'sini okur."""
    df = pd.read_csv(path)
    df.columns = [c.lower() for c in df.columns]
    ts = df["timestamp"]
    if pd.api.types.is_numeric_dtype(ts):
        idx = pd.to_datetime(ts, unit="ms", utc=True)
    else:
        idx = pd.to_datetime(ts, utc=True)
    df = df[["funding_rate"]].astype(float)
    idx = pd.DatetimeIndex(idx)
    try:
        idx = idx.as_unit("ns")
    except AttributeError:
        pass
    df.index = idx
    df = df[~df.index.duplicated(keep="first")].sort_index()
    return df


def get_ohlcv(
    exchange: str,
    symbol: str,
    interval: str,
    start: str,
    end: str,
    refresh: bool = False,
    pause: float = 0.25,
) -> pd.DataFrame:
    """OHLCV getirir; onbellekte varsa tekrar indirmez (refresh=True ile zorlar).

    Sembol delist oldugunda API bos doner. Bu durumda onbellekteki veri
    SILINMEZ; eksik kismi indirilemiyorsa onbellek aynen dondurulur.
    """
    path = cache_path(exchange, symbol, interval)
    start_ts = pd.Timestamp(start, tz="UTC")
    end_ts = pd.Timestamp(end, tz="UTC")
    start_ms = int(start_ts.timestamp() * 1000)
    end_ms = int(end_ts.timestamp() * 1000)

    cached: pd.DataFrame | None = None
    if path.exists():
        try:
            cached = load_csv(path)
        except Exception:
            cached = None

    if cached is not None and len(cached) and not refresh:
        if cached.index[0] <= start_ts and \
                cached.index[-1] >= end_ts - pd.Timedelta(days=2):
            return cached
        # kismi veri: mevcut olani koru, eksik kismi indir
        start_ms = int(cached.index[-1].timestamp() * 1000) + 1
        if start_ms >= end_ms:
            return cached

    if exchange == "binance":
        fresh = download_binance_ohlcv(symbol, interval, start_ms, end_ms, pause)
    elif exchange == "bybit":
        fresh = download_bybit_ohlcv(symbol, interval, start_ms, end_ms, pause)
    else:
        raise MarketError(f"Bilinmeyen borsa: {exchange}")

    if len(fresh) == 0:
        # API bos dondu (delist / gecici hata): onbellekteki veriyi KORU
        if cached is not None and len(cached):
            return cached
        return fresh

    if cached is not None and len(cached):
        fresh = pd.concat([cached, fresh])
        fresh = fresh[~fresh.index.duplicated(keep="last")].sort_index()
    save_csv(fresh, path)
    return fresh


def get_funding(exchange: str, symbol: str, start: str, end: str,
                refresh: bool = False) -> pd.DataFrame:
    """Funding oranlari (perpetual). Binance uzerinden; Bybit icin Bos gecer."""
    path = cache_path(exchange, symbol, "8h", kind="funding")
    start_ts = pd.Timestamp(start, tz="UTC")
    end_ts = pd.Timestamp(end, tz="UTC")

    cached = load_funding_csv(path) if path.exists() else pd.DataFrame()
    if len(cached) and not refresh:
        # onbellek istenen araligi kapsiyorsa tekrar indirme
        if cached.index[0] <= start_ts and cached.index[-1] >= end_ts - pd.Timedelta(days=2):
            return cached
        if cached.index[-1] >= end_ts:
            return cached

    if exchange != "binance":
        return pd.DataFrame(columns=["funding_rate"], index=pd.DatetimeIndex([], tz="UTC"))

    start_ms = int(start_ts.timestamp() * 1000)
    end_ms = int(end_ts.timestamp() * 1000)
    fresh = download_binance_funding(symbol, start_ms, end_ms)
    if len(cached):
        fresh = pd.concat([cached, fresh])
        fresh = fresh[~fresh.index.duplicated(keep="last")].sort_index()
    if len(fresh):
        save_funding_csv(fresh, path)
    return fresh


# --------------------------------------------------------------------------
# dogrulama
# --------------------------------------------------------------------------

def validate_ohlcv(df: pd.DataFrame, interval: str) -> dict:
    """Veri sagligi: siralama, OHLC tutarliligi, bosluklar, tekrar."""
    problems: list[str] = []
    if len(df) == 0:
        return {"rows": 0, "problems": ["bos veri"], "gaps": 0,
                "start": None, "end": None, "coverage_pct": 0.0}
    if not df.index.is_monotonic_increasing:
        problems.append("index sirali degil")
    bad = ((df["high"] < df["low"]) | (df["close"] > df["high"]) |
           (df["close"] < df["low"]) | (df["open"] > df["high"]) |
           (df["open"] < df["low"])).sum()
    if bad:
        problems.append(f"{int(bad)} tutarsiz OHLC satiri")
    nonpos = (df[["open", "high", "low", "close"]] <= 0).any(axis=1).sum()
    if nonpos:
        problems.append(f"{int(nonpos)} sifir/negatif fiyat satiri")
    expected = pd.Timedelta(milliseconds=TF_MS[interval])
    diffs = df.index.to_series().diff()
    gaps = int((diffs > expected).sum())
    dup = int(df.index.duplicated().sum())
    if dup:
        problems.append(f"{dup} tekrar eden zaman damgasi")
    return {
        "rows": len(df),
        "start": str(df.index[0]),
        "end": str(df.index[-1]),
        "gaps": gaps,
        "duplicates": dup,
        "problems": problems,
    }


def list_perp_symbols(exchange: str = "binance", min_quote_volume_24h: float = 0.0) -> list[str]:
    """Islemde olan USDT perpetual sembolleri (fiyat/hacim metrikleriyle)."""
    if exchange == "binance":
        data = _http_json(f"{BINANCE_FAPI}/fapi/v1/ticker/24hr", {})
        out = []
        for row in data:
            if row.get("symbol", "").endswith("USDT"):
                try:
                    qv = float(row.get("quoteVolume", 0))
                except (TypeError, ValueError):
                    qv = 0.0
                if qv >= min_quote_volume_24h:
                    out.append(row["symbol"])
        return sorted(set(out))
    if exchange == "bybit":
        data = _http_json(
            f"{BYBIT_V5}/v5/market/tickers", {"category": "linear"}
        )
        out = []
        for row in data.get("result", {}).get("list", []):
            if row.get("symbol", "").endswith("USDT"):
                try:
                    qv = float(row.get("turnover24h", 0))
                except (TypeError, ValueError):
                    qv = 0.0
                if qv >= min_quote_volume_24h:
                    out.append(row["symbol"])
        return sorted(set(out))
    raise MarketError(f"Bilinmeyen borsa: {exchange}")
