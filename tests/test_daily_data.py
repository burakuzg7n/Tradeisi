"""Plan B günlük veri: indirme ve E14 sağlık kontrolü testleri (sentetik veri)."""
from datetime import date, timedelta

import pandas as pd
import pytest

from tradebot import daily_data as dd

DAY = dd.DAY_MS


def ms(d: date) -> int:
    return dd.day_index(d) * DAY


def frame(start: date, end: date, skip=(), price=100.0) -> pd.DataFrame:
    rows = []
    d = start
    while d <= end:
        if d not in skip:
            rows.append([ms(d), price, price * 1.02, price * 0.98, price * 1.01, 10.0])
        d += timedelta(days=1)
    return pd.DataFrame(rows, columns=dd.COLUMNS)


FULL_START = date(2019, 10, 1)
FULL_END = date(2025, 6, 30)


def clean_frames():
    return {s: frame(FULL_START, FULL_END) for s in dd.SYMBOLS}


def test_clean_data_has_no_blockers():
    rep = dd.build_report(clean_frames())
    assert rep["verdict"] == "VERİ UYGUN"
    assert rep["blockers"] == []
    s = rep["symbols"]["BTCUSDT"]
    assert s["insample"]["expected_days"] == 1827  # 2020-01-01..2024-12-31
    assert s["insample"]["missing_days"] == 0
    assert s["insample_end_bar_present"] is True
    assert rep["common_holdout_end"] == "2025-06-30"


def test_insample_missing_threshold_is_strictly_more_than_one_percent():
    # 1827 günün %1'i = 18,27 → 18 eksik geçer, 19 eksik engellenir
    gap18 = {date(2021, 3, 1) + timedelta(days=i) for i in range(18)}
    gap19 = {date(2021, 3, 1) + timedelta(days=i) for i in range(19)}
    f = clean_frames()
    f["ETHUSDT"] = frame(FULL_START, FULL_END, skip=gap18)
    rep = dd.build_report(f)
    assert rep["blockers"] == []
    assert rep["symbols"]["ETHUSDT"]["insample"]["missing_days"] == 18
    assert rep["symbols"]["ETHUSDT"]["gaps_after_listing"] == [
        {"from": "2021-03-01", "to": "2021-03-18", "days": 18}]
    f["ETHUSDT"] = frame(FULL_START, FULL_END, skip=gap19)
    rep = dd.build_report(f)
    assert any("ETHUSDT: in-sample eksik gün oranı" in b for b in rep["blockers"])
    assert rep["verdict"] == "VERİ ENGELLİ"


def test_pre_listing_days_are_not_missing():
    f = clean_frames()
    f["SOLUSDT"] = frame(date(2020, 9, 14), FULL_END)
    rep = dd.build_report(f)
    s = rep["symbols"]["SOLUSDT"]
    assert rep["blockers"] == []
    assert s["insample"]["from"] == "2020-09-14"
    assert s["insample"]["expected_days"] == (date(2024, 12, 31) - date(2020, 9, 14)).days + 1
    assert s["missing_after_listing"] == 0
    # 55. bar = listeleme + 54 gün (bilgi amaçlı)
    assert s["warmup_55_bar_done"] == str(date(2020, 9, 14) + timedelta(days=54))


def test_missing_2024_12_31_bar_blocks_even_if_ratio_ok():
    f = clean_frames()
    f["BNBUSDT"] = frame(FULL_START, FULL_END, skip={date(2024, 12, 31)})
    rep = dd.build_report(f)
    assert "BNBUSDT: 2024-12-31 günlük barı yok (E14/3)" in rep["blockers"]
    assert rep["symbols"]["BNBUSDT"]["insample"]["missing_days"] == 1


def test_data_ending_before_2024_12_31_blocks():
    f = clean_frames()
    f["BNBUSDT"] = frame(FULL_START, date(2024, 12, 30))
    rep = dd.build_report(f)
    assert "BNBUSDT: 2024-12-31 günlük barı yok (E14/3)" in rep["blockers"]


def test_symbol_listed_after_insample_has_no_e14_3_blocker():
    f = clean_frames()
    f["BNBUSDT"] = frame(date(2025, 1, 10), FULL_END)
    rep = dd.build_report(f)
    assert not any("E14/3" in b for b in rep["blockers"])
    assert rep["symbols"]["BNBUSDT"]["insample"]["expected_days"] == 0


@pytest.mark.parametrize("mutate,label", [
    (lambda df: df.assign(high=df["high"].where(df.index != 5, 50.0)), "high < low"),
    (lambda df: df.assign(open=df["open"].where(df.index != 5, 0.0)), "sıfır/negatif fiyat"),
    (lambda df: df.assign(open=df["open"].where(df.index != 5, 200.0)), "open [low, high] dışında"),
    (lambda df: df.assign(close=df["close"].where(df.index != 5, 1.0)), "close [low, high] dışında"),
    (lambda df: df.assign(close=df["close"].where(df.index != 5, float("nan"))), "sayısal olmayan"),
    (lambda df: pd.concat([df, df.iloc[[5]]], ignore_index=True), "tekrarlanan zaman damgası"),
])
def test_bad_bars_block(mutate, label):
    f = clean_frames()
    f["ETHUSDT"] = mutate(frame(FULL_START, FULL_END))
    rep = dd.build_report(f)
    bad = rep["symbols"]["ETHUSDT"]["bad_bars"]
    assert any(label in b for b in bad), bad
    assert any("ETHUSDT" in b and "E14/2" in b for b in rep["blockers"])


def test_common_holdout_end_is_earliest_last_day_and_holdout_stats_use_it():
    f = clean_frames()
    f["SOLUSDT"] = frame(FULL_START, date(2025, 6, 20))
    f["BTCUSDT"] = frame(FULL_START, FULL_END, skip={date(2025, 6, 20)})
    rep = dd.build_report(f)
    assert rep["common_holdout_end"] == "2025-06-20"
    btc = rep["symbols"]["BTCUSDT"]
    assert btc["holdout"]["to"] == "2025-06-20"
    assert btc["holdout"]["expected_days"] == (date(2025, 6, 20) - date(2025, 1, 1)).days + 1
    assert btc["holdout"]["missing_days"] == 1
    assert btc["holdout_end_bar_present"] is False  # E13: bitişten önceki son barda tasfiye
    assert rep["symbols"]["SOLUSDT"]["holdout_end_bar_present"] is True


def test_holdout_missing_ratio_blocks():
    f = clean_frames()
    skip = {date(2025, 2, 1) + timedelta(days=i) for i in range(5)}  # 5/181 > %1
    f["ETHUSDT"] = frame(FULL_START, FULL_END, skip=skip)
    rep = dd.build_report(f)
    assert any("ETHUSDT: hold-out eksik gün oranı" in b for b in rep["blockers"])


def test_misaligned_timestamp_is_reported():
    f = clean_frames()
    df = frame(FULL_START, FULL_END)
    df.loc[3, "timestamp"] += 3_600_000
    f["BTCUSDT"] = df
    rep = dd.build_report(f)
    assert any("hizalı olmayan" in w for w in rep["symbols"]["BTCUSDT"]["warnings"])


def test_report_contains_no_performance_fields():
    rep = dd.build_report(clean_frames())
    text = str(rep).lower()
    for word in ("pnl", "profit", "pf", "drawdown", "trades", "equity"):
        assert f"'{word}'" not in text


# ---------------------------------------------------------------- indirme
class FakeResp:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


class FakeSession:
    def __init__(self, bars, info=None):
        self.bars = bars  # açılış ms listesi
        self.info = info
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, dict(params or {})))
        if url.endswith(dd.EXCHANGE_INFO_PATH):
            return FakeResp(self.info)
        start, limit = params["startTime"], params["limit"]
        sel = [b for b in self.bars if b >= start][:limit]
        return FakeResp([[b, "1", "2", "0.5", "1.5", "10", b + DAY - 1] for b in sel])


def test_download_paginates_and_drops_unclosed_bar():
    start = ms(date(2019, 9, 8))
    n = 3200  # > 2 sayfa
    bars = [start + i * DAY for i in range(n)]
    now = bars[-1] + DAY // 2  # son mum henüz kapanmadı
    sess = FakeSession(bars)
    rows = dd.download_daily_rows("BTCUSDT", sess, now, start_ms=start, sleep=lambda s: None)
    got = [int(r[0]) for r in rows]
    assert got == bars[:-1]
    assert len(sess.calls) == 3
    assert all(c[1]["interval"] == "1d" and c[1]["limit"] == dd.KLINES_LIMIT for c in sess.calls)
    assert all(c[0] == dd.FAPI_BASE + dd.KLINES_PATH for c in sess.calls)


def test_rows_roundtrip_through_csv(tmp_path):
    bars = [ms(date(2020, 1, 1)) + i * DAY for i in range(3)]
    rows = dd.download_daily_rows("X", FakeSession(bars), bars[-1] + DAY, start_ms=bars[0],
                                  sleep=lambda s: None)
    p = tmp_path / "X_1d.csv"
    dd.save_daily(dd.rows_to_frame(rows), p)
    df = dd.load_daily_raw(p)
    assert df["timestamp"].tolist() == bars
    assert df["close"].tolist() == [1.5, 1.5, 1.5]


def test_contracts_require_perpetual():
    info = {"symbols": [{"symbol": s, "contractType": "PERPETUAL", "onboardDate": 1, "status": "TRADING"}
                        for s in dd.SYMBOLS]}
    out = dd.fetch_contracts(FakeSession([], info))
    assert set(out) == set(dd.SYMBOLS)
    info["symbols"][1]["contractType"] = "CURRENT_QUARTER"
    with pytest.raises(dd.DataError, match="PERPETUAL"):
        dd.fetch_contracts(FakeSession([], info))
    info["symbols"].pop(1)
    with pytest.raises(dd.DataError, match="bulunamadı"):
        dd.fetch_contracts(FakeSession([], info))
