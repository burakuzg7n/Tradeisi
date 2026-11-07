"""Veri katmani — funding onbellegi ve indirme penceresi testleri."""
from __future__ import annotations

import pandas as pd
import pytest

from trader import market


# ---------------------------------------------------------------- onbellek

def _funding_frame() -> pd.DataFrame:
    idx = pd.DatetimeIndex(
        ["2023-01-01 00:00:00.002000", "2023-01-01 08:00:00.006000"],
        tz="UTC",
    )
    return pd.DataFrame({"funding_rate": [0.0001, 0.0002]}, index=idx)


def test_funding_csv_roundtrip(tmp_path):
    df = _funding_frame()
    path = tmp_path / "funding.csv"
    market.save_funding_csv(df, path)
    loaded = market.load_funding_csv(path)
    assert len(loaded) == 2
    assert list(loaded.columns) == ["funding_rate"]
    assert loaded.index[0] == df.index[0]
    assert loaded["funding_rate"].tolist() == [0.0001, 0.0002]


def test_funding_cache_path_is_separate_from_ohlcv():
    f = market.cache_path("binance", "BTCUSDT", "8h", kind="funding")
    o = market.cache_path("binance", "BTCUSDT", "1d")
    assert f != o
    assert "funding" in f.name


def test_get_funding_uses_cache_without_network(tmp_path, monkeypatch):
    monkeypatch.setattr(market, "DATA_DIR", tmp_path)
    path = market.cache_path("binance", "BTCUSDT", "8h", kind="funding")
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(
        {"funding_rate": [0.0001] * 300},
        index=pd.date_range("2023-01-01", periods=300, freq="8h", tz="UTC"),
    )
    market.save_funding_csv(df, path)

    def _boom(*args, **kwargs):  # pragma: no cover - agara dusmemeli
        raise AssertionError("cache varken agara cagrilmamali")

    monkeypatch.setattr(market, "download_binance_funding", _boom)
    # istenen aralik cache'in icinde -> agara gerek yok
    out = market.get_funding("binance", "BTCUSDT", "2023-01-01", "2023-04-01")
    assert len(out) == 300


def test_get_funding_bybit_returns_empty():
    out = market.get_funding("bybit", "BTCUSDT", "2023-01-01", "2023-02-01")
    assert len(out) == 0


# ---------------------------------------------------------------- ohlcv onbellegi

def _ohlcv_frame(n: int = 10, start: str = "2023-01-01") -> pd.DataFrame:
    idx = pd.date_range(start, periods=n, freq="1D", tz="UTC")
    return pd.DataFrame(
        {
            "open": [100.0] * n, "high": [101.0] * n, "low": [99.0] * n,
            "close": [100.5] * n, "volume": [10.0] * n,
        },
        index=idx,
    )


def test_get_ohlcv_keeps_cache_when_exchange_returns_empty(tmp_path, monkeypatch):
    """Delist olan sembolde API bos doner; onbellekteki veri SILINMEZ."""
    monkeypatch.setattr(market, "DATA_DIR", tmp_path)
    path = market.cache_path("binance", "OLDUSDT", "1d")
    path.parent.mkdir(parents=True, exist_ok=True)
    market.save_csv(_ohlcv_frame(10), path)

    monkeypatch.setattr(
        market, "download_binance_ohlcv",
        lambda *a, **k: market._empty_ohlcv(),
    )
    out = market.get_ohlcv("binance", "OLDUSDT", "1d", "2023-01-01", "2024-01-01")
    assert len(out) == 10
    assert out.index[-1] == pd.Timestamp("2023-01-10", tz="UTC")


def test_get_ohlcv_uses_cache_without_network(tmp_path, monkeypatch):
    monkeypatch.setattr(market, "DATA_DIR", tmp_path)
    path = market.cache_path("binance", "BTCUSDT", "1d")
    path.parent.mkdir(parents=True, exist_ok=True)
    market.save_csv(_ohlcv_frame(30), path)

    def _boom(*args, **kwargs):  # pragma: no cover - agara dusmemeli
        raise AssertionError("cache varken agara cagrilmamali")

    monkeypatch.setattr(market, "download_binance_ohlcv", _boom)
    out = market.get_ohlcv("binance", "BTCUSDT", "1d", "2023-01-01", "2023-01-30")
    assert len(out) == 30


def test_get_ohlcv_merges_new_rows_into_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(market, "DATA_DIR", tmp_path)
    path = market.cache_path("binance", "BTCUSDT", "1d")
    path.parent.mkdir(parents=True, exist_ok=True)
    market.save_csv(_ohlcv_frame(10), path)

    fresh = _ohlcv_frame(5, start="2023-01-11")
    monkeypatch.setattr(
        market, "download_binance_ohlcv", lambda *a, **k: fresh.copy()
    )
    out = market.get_ohlcv("binance", "BTCUSDT", "1d", "2023-01-01", "2023-01-20")
    assert len(out) == 15
    assert market.load_csv(path).index[-1] == pd.Timestamp("2023-01-15", tz="UTC")


# ---------------------------------------------------------------- indirme

class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_download_funding_walks_multiple_windows(monkeypatch):
    """1000 kayitlik pencere kullanilir; veri 2 pencerede gelir."""
    calls: list[dict] = []

    def fake_get(url, params=None, timeout=None):
        calls.append(params)
        start = int(params["startTime"])
        end = int(params["endTime"])
        # her 8 saatte bir kayit uret
        out = []
        t = start
        while t <= end and len(out) < 1000:
            out.append({"fundingTime": t, "fundingRate": 0.0001})
            t += 8 * 3600 * 1000
        return _FakeResponse(out)

    import requests

    monkeypatch.setattr(requests, "get", fake_get)
    start_ms = 0
    end_ms = 400 * 86_400_000  # 400 gun -> 2 pencereden fazla
    df = market.download_binance_funding("BTCUSDT", start_ms, end_ms, pause=0.0)
    assert len(df) > 1000
    assert len(calls) >= 2
    # her pencerede en fazla 1000 kayit istenir
    assert all(c["limit"] == 1000 for c in calls)


def test_download_funding_empty_result(monkeypatch):
    def fake_get(url, params=None, timeout=None):
        return _FakeResponse([])

    import requests

    monkeypatch.setattr(requests, "get", fake_get)
    df = market.download_binance_funding("BTCUSDT", 0, 10 * 86_400_000, pause=0.0)
    assert len(df) == 0
    assert list(df.columns) == ["funding_rate"]
