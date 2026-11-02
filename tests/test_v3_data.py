"""V3 veri sağlığı: 15m eksik/bozuk mum, listeleme, 2024-12-31 23:45 engeli, d_son."""
from datetime import date, timedelta

import pandas as pd
import pytest

from tradebot import v3_data as vd
from tradebot.strategy_v3 import BAR_MS, DAY_MS

INS = (date(2021, 1, 1), date(2021, 1, 10))
HO = date(2021, 1, 11)
START, END = date(2020, 12, 25), date(2021, 1, 15)
SYMS = vd.SYMBOLS


def ms(d, slot=0):
    return vd.day_index(d) * DAY_MS + slot * BAR_MS


def frame(start=START, end=END, drop=()):
    rows = []
    t, stop = ms(start), ms(end) + 96 * BAR_MS
    while t < stop:
        if t not in drop:
            rows.append([t, 1.0, 1.1, 0.9, 1.05, 5.0])
        t += BAR_MS
    return pd.DataFrame(rows, columns=vd.COLUMNS)


def contracts(**onb):
    return {s: {"contractType": "PERPETUAL", "status": "TRADING",
                "onboardDate": ms(onb.get(s, START))} for s in SYMS}


def rep(frames, **onb):
    return vd.build_report(frames, contracts(**onb), insample=INS, holdout_start=HO)


def clean():
    return {s: frame() for s in SYMS}


def test_clean_ok_and_d_son():
    r = rep(clean())
    assert r["verdict"] == "VERİ UYGUN" and r["d_son"] == "2021-01-15"
    assert r["symbols"]["XRPUSDT"]["insample"]["expected_bars"] == 10 * 96


def test_missing_threshold_strict_one_percent():
    exp = 10 * 96                                          # 960 → %1 = 9,6
    f = clean()
    f["ADAUSDT"] = frame(drop={ms(date(2021, 1, 5), s) for s in range(9)})
    assert rep(f)["blockers"] == []
    f["ADAUSDT"] = frame(drop={ms(date(2021, 1, 5), s) for s in range(10)})
    assert any("ADAUSDT: in-sample eksik" in b for b in rep(f)["blockers"])
    assert exp == 960


def test_insample_end_bar_required():
    f = clean()
    f["LINKUSDT"] = frame(drop={ms(INS[1], 95)})
    assert "LINKUSDT: 2021-01-10 23:45 mumu yok" in rep(f)["blockers"]


def test_truncated_start_counts_as_missing():
    f = clean()
    f["DOGEUSDT"] = frame(start=date(2021, 1, 6))
    r = rep(f)
    assert r["symbols"]["DOGEUSDT"]["insample"]["missing_bars"] == 5 * 96
    assert any("DOGEUSDT: in-sample eksik" in b for b in r["blockers"])


def test_late_listing_not_missing():
    f = clean()
    f["AVAXUSDT"] = frame(start=date(2021, 1, 6))
    r = rep(f, AVAXUSDT=date(2021, 1, 6))
    assert r["symbols"]["AVAXUSDT"]["insample"]["missing_bars"] == 0
    assert r["blockers"] == []


def test_missing_listing_info_blocks():
    c = contracts()
    c["XRPUSDT"]["onboardDate"] = None
    r = vd.build_report(clean(), c, insample=INS, holdout_start=HO)
    assert any("XRPUSDT: listeleme" in b for b in r["blockers"])


@pytest.mark.parametrize("mut,label", [
    (lambda df: df.assign(high=df["high"].where(df.index != 7, 0.5)), "high < low"),
    (lambda df: df.assign(open=df["open"].where(df.index != 7, 0.0)), "sıfır/negatif"),
    (lambda df: df.assign(close=df["close"].where(df.index != 7, float("inf"))), "sonlu olmayan"),
    (lambda df: df.assign(open=df["open"].where(df.index != 7, 2.0)), "open [low, high]"),
    (lambda df: pd.concat([df, df.iloc[[7]]], ignore_index=True), "tekrarlanan"),
])
def test_bad_bars_block(mut, label):
    f = clean()
    f["XRPUSDT"] = mut(frame())
    r = rep(f)
    assert any(label in b for b in r["symbols"]["XRPUSDT"]["bad_bars"])
    assert any("XRPUSDT" in b and "bozuk" in b for b in r["blockers"])


def test_d_son_requires_2345_in_all_and_last_full_day():
    f = clean()
    f["ADAUSDT"] = frame(drop={ms(END, 95)})                # ADA'nın son günü tam değil → ≤ 14
    f["XRPUSDT"] = frame(drop={ms(END - timedelta(days=1), 95)})   # 14'te XRP 23:45 yok
    r = rep(f)
    assert r["d_son"] == "2021-01-13"
    assert r["symbols"]["XRPUSDT"]["holdout"]["expected_bars"] == 3 * 96


def test_holdout_missing_ratio_blocks():
    f = clean()
    f["LINKUSDT"] = frame(drop={ms(date(2021, 1, 12), s) for s in range(10, 20)})  # 10/480 > %1
    assert any("LINKUSDT: hold-out eksik" in b for b in rep(f)["blockers"])


def test_download_pages_and_drops_unclosed():
    class R:
        def __init__(s, d): s.d = d
        def raise_for_status(s): pass
        def json(s): return s.d

    class S:
        def __init__(s, bars): s.bars, s.n = bars, 0
        def get(s, url, params=None, timeout=None):
            s.n += 1
            sel = [b for b in s.bars if b >= params["startTime"]][:params["limit"]]
            assert params["interval"] == "15m"
            return R([[b, "1", "1.1", "0.9", "1", "5"] for b in sel])

    bars = [ms(START) + k * BAR_MS for k in range(3200)]
    now = bars[-1] + BAR_MS // 2
    rows = vd.download_15m_rows("X", S(bars), now, bars[0], sleep=lambda s: None)
    assert [int(r[0]) for r in rows] == bars[:-1]


def test_load_15m_roundtrip(tmp_path):
    p = tmp_path / "X_15m.csv"
    frame(start=START, end=START).to_csv(p, index=False)
    df = vd.load_15m(p)
    assert len(df) == 96 and df.index[0] == ms(START)
