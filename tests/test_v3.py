"""V3: strateji (niyet) ve 15m motoru — sayısal beklenen sonuçlu sentetik testler."""
import math

import numpy as np
import pandas as pd
import pytest

from tradebot import strategy_v3 as sv
from tradebot.engine_v3 import V3Params, funding_count, newey_west_t, run_v3
from tradebot.strategy_v3 import BAR_MS, DAY_MS, Intent

NOCOST = V3Params(taker_fee=0.0, maker_fee=0.0, slippage=0.0, funding_rate=0.0)
FULL = V3Params()
D = 20_000


def ts(day, slot):
    return day * DAY_MS + slot * BAR_MS


def bars(days, price=100.0, over=None, drop=()):
    """days: gün listesi; her gün 96 mum düz fiyat (h=p+0,5, l=p−0,5).
    over: {(gün, slot): dict}; drop: {(gün, slot)} eksik mumlar."""
    over = over or {}
    rows, idx = [], []
    for d in days:
        for s in range(96):
            if (d, s) in drop:
                continue
            r = dict(open=price, high=price + 0.5, low=price - 0.5, close=price)
            r.update(over.get((d, s), {}))
            rows.append(r)
            idx.append(ts(d, s))
    return pd.DataFrame(rows, index=pd.Index(idx))


def flat_after(day, from_slot, price, h=0.5, lo=0.5):
    return {(day, s): dict(open=price, high=price + h, low=price - lo, close=price)
            for s in range(from_slot, 96)}


def long_setup(extra=None, drop=()):
    """D günü: Asya 100±0,5 → AH=100,5; tetik intent elle: P=102, M=100; dolum slot 31."""
    over = flat_after(D, 31, 103.0)
    over[(D, 31)] = dict(open=102.0, high=103.5, low=101.5, close=103.0)
    over.update(extra or {})
    df = bars([D], over=over, drop=drop)
    it = Intent("XRPUSDT", D, "long", ts(D, 30), 102.0, 100.0)
    return {"XRPUSDT": df}, {"XRPUSDT": [it]}


# ------------------------------------------------------------------ motor: temel
def test_long_target_no_cost():
    b, i = long_setup({(D, 40): dict(open=103, high=106.5, low=102.5, close=106)})
    r = run_v3(b, i, D, D, NOCOST)
    (t,) = r.trades
    assert (t.entry, t.stop, t.target, t.qty, t.risk_usd) == (102.0, 100.0, 106.0, 50.0, 100.0)
    assert (t.reason, t.exit, t.acct_day) == ("target", 106.0, D)
    assert t.pnl == pytest.approx(200.0) and t.r == pytest.approx(2.0)


def test_long_target_full_costs_exact():
    b, i = long_setup({(D, 40): dict(open=103, high=106.5, low=102.5, close=106)})
    r = run_v3(b, i, D, D, FULL)
    (t,) = r.trades
    F = 102 * 1.0003
    T = F + 2 * (F - 100)
    q = 50.0
    exp = (T - F) * q - F * q * 0.00055 - T * q * 0.0002 - F * q * 0.0001 * 1   # 08:00 funding
    assert t.entry == pytest.approx(F) and t.target == pytest.approx(T) and t.exit == pytest.approx(T)
    assert t.funding == pytest.approx(F * q * 0.0001)
    assert t.pnl == pytest.approx(exp)


def test_stop_priority_and_price_with_costs():
    b, i = long_setup({(D, 35): dict(open=103, high=110, low=99, close=103)})
    r = run_v3(b, i, D, D, FULL)
    (t,) = r.trades
    F = 102 * 1.0003
    assert t.reason == "stop" and t.exit == pytest.approx(100 * (1 - 0.0003))
    exp = (100 * 0.9997 - F) * 50 - F * 50 * 0.00055 - 100 * 0.9997 * 50 * 0.00055 - F * 50 * 0.0001
    assert t.pnl == pytest.approx(exp)


def test_target_requires_strict_exceed():
    b, i = long_setup({(D, 40): dict(open=103, high=106.0, low=102.5, close=105)})
    r = run_v3(b, i, D, D, NOCOST)
    assert r.trades[0].reason == "time_exit"


def test_gap_stop_and_gap_target():
    b, i = long_setup({(D, 40): dict(open=99, high=99.5, low=98, close=99)})
    t = run_v3(b, i, D, D, FULL).trades[0]
    assert t.reason == "gap_stop" and t.exit == pytest.approx(99 * 0.9997)
    b, i = long_setup({(D, 40): dict(open=108, high=109, low=107.5, close=108)})
    t = run_v3(b, i, D, D, FULL).trades[0]
    F = 102 * 1.0003
    assert t.reason == "gap_target" and t.exit == pytest.approx(F + 2 * (F - 100))
    assert t.exit_fee == pytest.approx(t.exit * t.qty * 0.0002)        # maker, slippage yok


def test_gap_through_stop_on_entry_bar_even_if_fill_inside():
    """ChatGPT örneği: P=102, M=100,02, açılış 100 → F=100,03 > M ama açılış ≤ M → acil çıkış."""
    over = flat_after(D, 31, 101.0)
    over[(D, 31)] = dict(open=100.0, high=101, low=99.8, close=100.5)
    df = bars([D], over=over)
    it = Intent("XRPUSDT", D, "long", ts(D, 30), 102.0, 100.02)
    r = run_v3({"XRPUSDT": df}, {"XRPUSDT": [it]}, D, D, FULL)
    (t,) = r.trades
    assert t.entry == pytest.approx(100.03) and t.entry > 100.02
    assert t.reason == "gap_through_stop" and t.exit == pytest.approx(100 * 0.9997)


def test_short_symmetric_stop():
    over = flat_after(D, 31, 97.0)
    over[(D, 31)] = dict(open=98.0, high=98.5, low=96.5, close=97)
    over[(D, 50)] = dict(open=97, high=100.5, low=96.8, close=97)
    df = bars([D], over=over)
    it = Intent("XRPUSDT", D, "short", ts(D, 30), 98.0, 100.0)
    t = run_v3({"XRPUSDT": df}, {"XRPUSDT": [it]}, D, D, NOCOST).trades[0]
    assert (t.entry, t.target, t.reason, t.exit) == (98.0, 94.0, "stop", 100.0)
    assert t.pnl == pytest.approx(-100.0)


# ------------------------------------------------------------------ zaman çıkışı / funding / gün
def test_time_exit_close_funding_and_day():
    b, i = long_setup()
    r = run_v3(b, i, D, D, FULL)
    (t,) = r.trades
    F = 102 * 1.0003
    assert t.reason == "time_exit" and t.acct_day == D
    assert t.exit == pytest.approx(103 * 0.9997)
    assert t.exit_ts == ts(D + 1, 0)
    assert t.funding == pytest.approx(F * 50 * 0.0001 * 3)       # 08:00, 16:00, 00:00


def test_deferred_time_exit_next_day_open():
    days = [D, D + 1]
    over = flat_after(D, 31, 103.0)
    over[(D, 31)] = dict(open=102.0, high=103.5, low=101.5, close=103.0)
    over[(D + 1, 0)] = dict(open=110.0, high=111, low=99, close=110)   # hedef/stop ötesi ama (0) önce
    df = bars(days, over=over, drop={(D, 95)})
    it = Intent("XRPUSDT", D, "long", ts(D, 30), 102.0, 100.0)
    r = run_v3({"XRPUSDT": df}, {"XRPUSDT": [it]}, D, D + 1, NOCOST)
    (t,) = r.trades
    assert t.reason == "time_exit_deferred" and t.exit == 110.0
    assert t.acct_day == D + 1 and t.exit_ts == ts(D + 1, 0)
    assert r.counters["time_exit_deferred"] == 1


def test_missing_fill_bar_cancels_without_cost():
    b, i = long_setup(drop={(D, 31)})
    r = run_v3(b, i, D, D, FULL)
    assert r.trades == [] and r.counters["orders_cancelled_missing_fill_bar"] == 1
    assert r.equity.iloc[-1] == pytest.approx(10_000)


def test_funding_count():
    h = 3_600_000
    base = D * DAY_MS
    assert funding_count(base + 7 * h, base + 7 * h + 1) == 0
    assert funding_count(base + 8 * h, base + 8 * h) == 1              # tam an: ödenir
    assert funding_count(base + 7 * h + 45 * 60_000, base + 24 * h) == 3
    assert funding_count(base, base + 24 * h) == 4


# ------------------------------------------------------------------ portföy muhasebesi
def test_sizing_after_exits_at_same_timestamp():
    """ADA'nın tetiği slot 40 kapanışında; XRP aynı damgada hedefte kapanır (+200).
    ADA boyutu güncel bakiyeden (10.200): risk 102."""
    b, i = long_setup({(D, 40): dict(open=103, high=106.5, low=102.5, close=106)})
    ada = bars([D], over={**flat_after(D, 41, 51.0), (D, 41): dict(open=51, high=51.4, low=50.6, close=51)})
    b["ADAUSDT"] = ada
    i["ADAUSDT"] = [Intent("ADAUSDT", D, "long", ts(D, 40), 51.0, 50.0)]
    r = run_v3(b, i, D, D, NOCOST)
    ada_t = [t for t in r.trades if t.symbol == "ADAUSDT"][0]
    assert ada_t.risk_usd == pytest.approx(102.0)
    assert ada_t.qty == pytest.approx(102.0)


def test_capital_exhaustion_blocks_and_flags():
    p = V3Params(taker_fee=0.0, maker_fee=0.0, slippage=0.0, funding_rate=0.0, risk_per_trade=2.0)
    b, i = long_setup({(D, 40): dict(open=50, high=50.5, low=49, close=50)})   # gap: (50−102)×10.000
    b["ADAUSDT"] = bars([D])
    i["ADAUSDT"] = [Intent("ADAUSDT", D, "long", ts(D, 45), 102.0, 100.0)]
    r = run_v3(b, i, D, D, p)
    assert r.trades[0].pnl < -10_000
    assert r.capital_exhausted is True and r.counters["orders_blocked_no_capital"] == 1


def test_mtm_carries_last_close_for_missing_bar_and_dd():
    b, i = long_setup(drop={(D, 50)})
    b["ADAUSDT"] = bars([D])
    r = run_v3(b, i, D, D, NOCOST)
    assert r.counters["mtm_carried_marks"] == 1
    assert r.equity.loc[ts(D, 50)] == pytest.approx(10_000 + (103 - 102) * 50)
    assert r.max_drawdown == pytest.approx(0.0, abs=1e-12)


def test_daily_series_all_days():
    b, i = long_setup({(D, 40): dict(open=103, high=106.5, low=102.5, close=106)})
    b["XRPUSDT"] = pd.concat([b["XRPUSDT"], bars([D + 1, D + 2])])
    r = run_v3(b, i, D, D + 2, NOCOST)
    s = r.daily_returns(10_000)
    assert list(s.index) == [D, D + 1, D + 2]
    assert s.tolist() == pytest.approx([0.02, 0.0, 0.0])


def test_open_position_at_end_raises():
    b, i = long_setup(drop={(D, 95)})
    with pytest.raises(RuntimeError, match="açık pozisyon"):
        run_v3(b, i, D, D, NOCOST)


def test_newey_west_matches_manual():
    rng = np.random.default_rng(0)
    x = rng.normal(0.001, 0.01, 1461)
    m, se, L, t = newey_west_t(x)
    assert L == 7
    e = x - x.mean()
    T = len(x)
    g = [e[k:] @ e[:T - k] / T for k in range(L + 1)]
    var = g[0] + 2 * sum((1 - k / (L + 1)) * g[k] for k in range(1, L + 1))
    assert se == pytest.approx(math.sqrt(var / T))
    assert t == pytest.approx(x.mean() / se)
    assert math.isnan(newey_west_t(np.zeros(100))[3])


# ------------------------------------------------------------------ strateji
def warm_days(n, start, closes):
    """n günlük ısınma; her günün kapanışı closes[k] (tüm mumlar o fiyatta)."""
    frames = [bars([start + k], price=closes[k]) for k in range(n)]
    return pd.concat(frames)


def test_daily_close_validity():
    df = pd.concat([bars([D]), bars([D + 1], drop={(D + 1, s) for s in range(6)}),
                    bars([D + 2], drop={(D + 2, s) for s in range(7)}),
                    bars([D + 3], drop={(D + 3, 95)})])
    c = sv.daily_closes(df)
    assert set(c) == {D, D + 1}                                     # 90 mum geçerli, 89 değil


def test_trend_sma_includes_yesterday():
    closes = {D - 20 + k: 100.0 for k in range(19)}
    closes[D - 1] = 120.0
    assert sv.trend_side(closes, D) == "long"                       # SMA = 101 < 120
    closes[D - 1] = 100.0
    assert sv.trend_side(closes, D) == "flat"
    del closes[D - 1]
    assert sv.trend_side(closes, D) is None


def _strategy_df(trigger_over, drop=()):
    warm = warm_days(20, D - 20, [90.0 + k * 0.5 for k in range(20)])   # yükselen → long
    over = {(D, s): dict(open=100, high=101, low=99, close=100) for s in range(28)}
    over.update(trigger_over)
    return pd.concat([warm, bars([D], price=100.0, over=over, drop=drop)])


def test_long_intent_first_trigger_exact():
    df = _strategy_df({(D, 33): dict(open=100, high=102.6, low=100, close=102.5),
                       (D, 40): dict(open=100, high=104, low=100, close=103.9)})
    log = []
    (it,) = sv.generate_intents("XRPUSDT", df, D, D, log)
    assert (it.side, it.trigger_ts, it.P, it.M) == ("long", ts(D, 33), 102.5, 100.0)
    assert log[-1].status == "intent"


def test_asia_bar_breakout_not_trigger_and_window_edges():
    df = _strategy_df({(D, 27): dict(open=100, high=101, low=99, close=100.9),
                       (D, 80): dict(open=100, high=110, low=100, close=109)})
    assert sv.generate_intents("XRPUSDT", df, D, D) == []           # 20:00 pencere dışı
    df = _strategy_df({(D, 79): dict(open=100, high=110, low=100, close=109)})
    (it,) = sv.generate_intents("XRPUSDT", df, D, D)
    assert it.trigger_ts == ts(D, 79)


def test_min_stop_and_missing_asia():
    log = []
    df = _strategy_df({(D, 33): dict(open=100, high=101.5, low=100, close=101.005)})  # (101,005−100)/101,005 < %1
    assert sv.generate_intents("XRPUSDT", df, D, D, log) == []
    assert log[-1].status == "min_stop"
    df = _strategy_df({(D, 33): dict(open=100, high=103, low=100, close=102.5)}, drop={(D, 5)})
    log = []
    assert sv.generate_intents("XRPUSDT", df, D, D, log) == [] and log[-1].status == "no_asia"


def test_first_trigger_failing_min_stop_ends_day():
    df = _strategy_df({(D, 33): dict(open=100, high=101.5, low=100, close=101.005),
                       (D, 40): dict(open=100, high=104, low=100, close=103.9)})
    assert sv.generate_intents("XRPUSDT", df, D, D) == []


def test_short_intent_with_falling_trend():
    warm = warm_days(20, D - 20, [110.0 - k * 0.5 for k in range(20)])
    over = {(D, s): dict(open=100, high=101, low=99, close=100) for s in range(28)}
    over[(D, 35)] = dict(open=100, high=100, low=97, close=97.5)
    df = pd.concat([warm, bars([D], over=over)])
    (it,) = sv.generate_intents("XRPUSDT", df, D, D)
    assert (it.side, it.P, it.M) == ("short", 97.5, 100.0)


def test_intents_no_lookahead():
    rng = np.random.default_rng(3)
    days = list(range(D - 25, D + 10))
    n = len(days) * 96
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.004, n)))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) * 1.002
    lw = np.minimum(o, c) * 0.998
    idx = [ts(d, s) for d in days for s in range(96)]
    df = pd.DataFrame(dict(open=o, high=h, low=lw, close=c), index=pd.Index(idx))
    full = sv.generate_intents("X", df, D - 3, D + 9)
    assert full, "test verisi en az bir niyet üretmeli"
    for it in full:
        part = sv.generate_intents("X", df[df.index <= it.trigger_ts], it.day, it.day)
        assert part == [it]
        pert = df.copy()
        pert.loc[pert.index > it.trigger_ts, ["open", "high", "low", "close"]] *= 1.5
        assert it in sv.generate_intents("X", pert, it.day, it.day)


def test_open_equal_target_is_not_gap_target():
    b, i = long_setup({(D, 40): dict(open=106.0, high=106.0, low=105.5, close=105.8)})
    t = run_v3(b, i, D, D, NOCOST).trades[0]
    assert t.reason == "time_exit"


def test_trigger_uses_close_not_wick():
    df = _strategy_df({(D, 33): dict(open=100, high=103, low=100, close=100.8),
                       (D, 40): dict(open=100, high=103, low=100, close=102.5)})
    (it,) = sv.generate_intents("XRPUSDT", df, D, D)
    assert it.trigger_ts == ts(D, 40)


def test_synthetic_generator_shape_and_determinism():
    from tradebot.synthetic_v3 import generate
    a = generate(("A", "B"), D, 3, 0.04, 0.5, "trend", 7)
    b = generate(("A", "B"), D, 3, 0.04, 0.5, "trend", 7)
    assert len(a["A"]) == 3 * 96 and a["A"].index[0] == ts(D, 0)
    pd.testing.assert_frame_equal(a["A"], b["A"])
    df = a["B"]
    assert (df["high"] >= df[["open", "close"]].max(axis=1)).all()
    assert (df["low"] <= df[["open", "close"]].min(axis=1)).all()
