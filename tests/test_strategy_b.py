"""Plan B sinyalleri: kanal/ATR sayısal doğruluk, E5 ısınma, eksik gün, lookahead."""
import numpy as np
import pandas as pd
import pytest

from tradebot import strategy_b as sb
from tradebot.portfolio_b import PlanBParams, run_portfolio

NOCOST = PlanBParams(taker_fee=0.0, slippage_rate=0.0, funding_per_day=0.0)


def rand_df(n=300, seed=1, start_day=18000, skip=()):
    rng = np.random.default_rng(seed)
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.03, n)))
    o = np.r_[c[0], c[:-1]] * (1 + rng.normal(0, 0.005, n))
    h = np.maximum(o, c) * (1 + rng.uniform(0, 0.02, n))
    l = np.minimum(o, c) * (1 - rng.uniform(0, 0.02, n))
    days = [start_day + i for i in range(n)]
    df = pd.DataFrame(dict(open=o, high=h, low=l, close=c), index=pd.Index(days))
    return df.drop(index=[start_day + k for k in skip])


def manual_atr(h, l, c, n=20):
    tr = [None] + [max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
                   for i in range(1, len(c))]
    atr = [None] * len(c)
    if len(c) > n:
        atr[n] = sum(tr[1:n + 1]) / n
        for i in range(n + 1, len(c)):
            atr[i] = (atr[i - 1] * (n - 1) + tr[i]) / n
    return atr


def test_channels_exact_and_exclude_today():
    df = rand_df(120)
    out = sb.compute_signals(df)
    h, l = df["high"].to_numpy(), df["low"].to_numpy()
    assert np.isnan(out["entry_channel"].iloc[54])
    for i in (55, 56, 80, 119):
        assert out["entry_channel"].iloc[i] == pytest.approx(h[i - 55:i].max())
    assert np.isnan(out["exit_channel"].iloc[19])
    for i in (20, 21, 90, 119):
        assert out["exit_channel"].iloc[i] == pytest.approx(l[i - 20:i].min())


def test_wilder_atr_exact():
    df = rand_df(200, seed=7)
    out = sb.compute_signals(df)
    exp = manual_atr(df["high"].tolist(), df["low"].tolist(), df["close"].tolist())
    assert np.isnan(out["atr"].iloc[19])
    for i in range(20, 200):
        assert out["atr"].iloc[i] == pytest.approx(exp[i], rel=1e-12)


def test_wilder_atr_small_hand_example():
    h = np.array([10.0, 12, 11, 15, 14])
    l = np.array([8.0, 9, 9, 10, 12])
    c = np.array([9.0, 11, 10, 14, 13])
    # TR: bar1 = max(3, 3, 0)=3; bar2 = max(2, 0, 2)=2; bar3 = max(5, 5, 0)=5; bar4 = max(2, 0, 2)=2
    atr = sb.wilder_atr(h, l, c, n=3)
    assert np.isnan(atr[:3]).all()
    assert atr[3] == pytest.approx((3 + 2 + 5) / 3)
    assert atr[4] == pytest.approx((10 / 3 * 2 + 2) / 3)


def _flat(n, price=100.0, start_day=18000):
    days = [start_day + i for i in range(n)]
    return pd.DataFrame(dict(open=price, high=price + 1, low=price - 1, close=price),
                        index=pd.Index(days), dtype=float)


def test_entry_signal_strict_and_needs_55_bars():
    df = _flat(80)
    df.iloc[54, df.columns.get_loc("close")] = 500.0   # 55. bar: geçmiş 54 bar → sinyal yok
    df.iloc[60, df.columns.get_loc("close")] = 101.0   # = kanal (101): eşitlik sinyal değil
    df.iloc[61, df.columns.get_loc("close")] = 101.01  # > kanal → sinyal
    df.iloc[61, df.columns.get_loc("high")] = 101.5
    out = sb.compute_signals(df)
    assert not out["entry_signal"].iloc[54]
    # 54. barın high'ı 101 kaldı (yalnız close değişti) → kanal 101
    assert out["entry_channel"].iloc[60] == pytest.approx(101.0)
    assert not out["entry_signal"].iloc[60]
    assert out["entry_signal"].iloc[61]
    assert out["entry_signal"].sum() == 1


def test_exit_signal_strict():
    df = _flat(40)
    df.iloc[25, df.columns.get_loc("close")] = 99.0     # = kanal (99) → sinyal yok
    df.iloc[26, df.columns.get_loc("close")] = 98.99
    df.iloc[26, df.columns.get_loc("low")] = 98.5
    out = sb.compute_signals(df)
    assert not out["exit_signal"].iloc[19]
    assert not out["exit_signal"].iloc[25]
    assert out["exit_signal"].iloc[26]
    assert out["exit_signal"].sum() == 1


def test_missing_days_counted_as_available_bars():
    df = rand_df(150, seed=3, skip=(30, 31, 32, 70))
    out = sb.compute_signals(df)
    h, l, c = df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy()
    for i in (55, 60, 100, len(df) - 1):
        assert out["entry_channel"].iloc[i] == pytest.approx(h[i - 55:i].max())
        assert out["exit_channel"].iloc[i] == pytest.approx(l[i - 20:i].min())
    exp = manual_atr(list(h), list(l), list(c))
    assert out["atr"].iloc[-1] == pytest.approx(exp[-1], rel=1e-12)


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_no_lookahead_truncation(seed):
    df = rand_df(260, seed=seed, skip=(40, 100))
    full = sb.compute_signals(df)
    for k in (20, 54, 55, 56, 75, 150, len(df) - 2):
        part = sb.compute_signals(df.iloc[:k + 1])
        pd.testing.assert_frame_equal(part, full.iloc[:k + 1])


def test_no_lookahead_future_perturbation():
    df = rand_df(200, seed=5)
    base = sb.compute_signals(df)
    df2 = df.copy()
    df2.iloc[121:] = df2.iloc[121:] * 3.0                  # 121 ve sonrası değişir
    pert = sb.compute_signals(df2)
    pd.testing.assert_frame_equal(base.iloc[:121], pert.iloc[:121])


def test_unsorted_index_rejected():
    df = rand_df(60).iloc[::-1]
    with pytest.raises(ValueError):
        sb.compute_signals(df)


def test_load_daily_roundtrip_and_alignment(tmp_path):
    days = [18000, 18001, 18003]
    p = tmp_path / "BTCUSDT_1d.csv"
    pd.DataFrame(dict(timestamp=[d * sb.DAY_MS for d in days], open=1.0, high=2.0, low=0.5,
                      close=1.5, volume=10.0)).to_csv(p, index=False)
    df = sb.load_daily(p)
    assert df.index.tolist() == days
    bad = tmp_path / "X_1d.csv"
    pd.DataFrame(dict(timestamp=[18000 * sb.DAY_MS + 3_600_000], open=1.0, high=2.0, low=0.5,
                      close=1.5, volume=1.0)).to_csv(bad, index=False)
    with pytest.raises(ValueError, match="hizalı"):
        sb.load_daily(bad)


def test_integration_breakout_trade_with_engine(tmp_path):
    n = 80
    df = _flat(n)
    df.iloc[60, df.columns.get_loc("close")] = 105.0   # kanal 101 → sinyal 60. bar
    df.iloc[60, df.columns.get_loc("high")] = 106.0
    df.iloc[61, df.columns.get_loc("open")] = 105.0
    df.iloc[61, df.columns.get_loc("close")] = 105.0
    df.iloc[61, df.columns.get_loc("high")] = 106.0
    df.iloc[61, df.columns.get_loc("low")] = 104.0
    p = tmp_path / "BTCUSDT_1d.csv"
    out = df.copy()
    out.insert(0, "timestamp", np.array(df.index) * sb.DAY_MS)
    out["volume"] = 1.0
    out.to_csv(p, index=False)
    frames = sb.build_frames(tmp_path, ["BTCUSDT"])
    sig = frames["BTCUSDT"]
    assert sig["entry_signal"].sum() == 1
    atr60 = sig["atr"].iloc[60]
    start, end = int(df.index[0]), int(df.index[-1])
    r = run_portfolio(frames, start, end, NOCOST)
    t = r.trades[0]
    assert t.entry_day == int(df.index[61])
    assert t.entry == pytest.approx(105.0)
    assert t.stop == pytest.approx(105.0 - 2 * atr60)
    assert t.qty == pytest.approx(50.0 / (2 * atr60))
