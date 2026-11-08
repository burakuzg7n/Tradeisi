"""Sepet momentum stratejisi — kurallar ve lookahead korumasi."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from trader.strategies.basket_momentum import BasketMomentum
from trader.strategy import Panel


def daily_series(n: int, start: float, end: float, volume: float,
                 start_date: str = "2023-01-02", noise: float = 0.0,
                 seed: int = 3) -> pd.DataFrame:
    """Duz trendli gunluk seri (volume sabit). `noise` oynaklik ekler."""
    idx = pd.date_range(start_date, periods=n, freq="1D", tz="UTC")
    close = np.linspace(start, end, n)
    if noise:
        rng = np.random.default_rng(seed)
        close = close * (1 + rng.normal(0, noise, n))
    return pd.DataFrame({
        "open": close, "high": close * 1.01, "low": close * 0.99,
        "close": close, "volume": volume,
    }, index=idx)


# 120 gun: 2023-01-02 (Pazartesi) baslar, son bar 2023-05-01 (Pazartesi) olur
# (n-1 = 119, 119 % 7 == 0 -> ayni hafta gunu)
N_DAYS = 120


@pytest.fixture
def panel_data():
    return {
        "A": daily_series(N_DAYS, 100, 200, 5000),              # guclu yukselis
        "B": daily_series(N_DAYS, 200, 100, 5000),              # guclu dusus
        "C": daily_series(N_DAYS, 100, 120, 5000),              # orta yukselis
        "D": daily_series(N_DAYS, 100, 100, 10, noise=0.002),   # duz, dusuk hacim
        "E": daily_series(N_DAYS, 100, 98, 4000, noise=0.004),   # duz, orta hacim
    }


@pytest.fixture
def last_ts(panel_data):
    """Son bar = 2023-05-01 (Pazartesi)."""
    return panel_data["A"].index[-1]


def test_universe_selected_by_volume(panel_data, last_ts):
    strat = BasketMomentum(universe_size=3, long_leg=1, short_leg=1)
    signals = strat.generate(Panel(panel_data), last_ts)
    universe = {s.symbol for s in signals if s.meta.get("in_universe")}
    assert universe == {"A", "B", "C"}       # D ve E dusuk hacim -> disarida


def test_long_top_short_bottom(panel_data, last_ts):
    strat = BasketMomentum(universe_size=3, long_leg=1, short_leg=1)
    signals = {s.symbol: s for s in strat.generate(Panel(panel_data), last_ts)}
    assert signals["A"].side == "long"
    assert signals["A"].weight > 0
    assert signals["B"].side == "short"
    assert signals["B"].weight < 0
    assert signals["C"].side == "flat"
    assert signals["C"].weight == 0.0


def test_net_exposure_approximately_zero(panel_data, last_ts):
    strat = BasketMomentum(universe_size=3, long_leg=1, short_leg=1,
                           gross_leverage=2.0)
    signals = strat.generate(Panel(panel_data), last_ts)
    net = sum(s.weight or 0.0 for s in signals)
    gross = sum(abs(s.weight or 0.0) for s in signals)
    assert net == pytest.approx(0.0, abs=1e-9)
    assert gross == pytest.approx(2.0, abs=1e-9)


def test_inverse_vol_weights_sum_to_one_per_leg(panel_data, last_ts):
    strat = BasketMomentum(universe_size=4, long_leg=2, short_leg=2)
    signals = strat.generate(Panel(panel_data), last_ts)
    long_w = sum(s.weight for s in signals if s.side == "long")
    short_w = sum(abs(s.weight) for s in signals if s.side == "short")
    # her bacak brutun yarisi
    assert long_w == pytest.approx(1.0, abs=1e-9)
    assert short_w == pytest.approx(1.0, abs=1e-9)


def test_rebalance_only_on_monday(panel_data, last_ts):
    strat = BasketMomentum(universe_size=3, long_leg=1, short_leg=1)
    assert last_ts.weekday() == 0, "test verisi Pazartesi ile bitmeli"
    assert strat.generate(Panel(panel_data), last_ts), "Pazartesi sinyal uretmeli"
    sunday = last_ts - pd.Timedelta(days=1)
    assert strat.generate(Panel(panel_data), sunday) == [], \
        "Pazartesi disi sinyal uretilmemeli"


def test_no_lookahead_future_data_does_not_change_signals(panel_data, last_ts):
    """Gelecege bakan veri eklendiginde sinyal DEGISMEZ."""
    strat = BasketMomentum(universe_size=3, long_leg=1, short_leg=1)
    base = {s.symbol: s.weight for s in strat.generate(Panel(panel_data), last_ts)}

    future = {}
    for sym, df in panel_data.items():
        extra = df.copy()
        row = extra.iloc[-1].copy()
        row["close"] = row["close"] * 100
        row["high"] = row["high"] * 100
        row["low"] = row["low"] * 100
        row["open"] = row["open"] * 100
        extra = pd.concat(
            [extra, pd.DataFrame([row], index=[last_ts + pd.Timedelta(days=1)])]
        )
        future[sym] = extra
    strat2 = BasketMomentum(universe_size=3, long_leg=1, short_leg=1)
    with_future = {s.symbol: s.weight
                   for s in strat2.generate(Panel(future), last_ts)}
    assert base == with_future


def test_momentum_skips_recent_week(panel_data, last_ts):
    """skip=7: son 7 gun momentum hesabina dahil DEGILDIR."""
    strat = BasketMomentum(universe_size=3, long_leg=1, short_leg=1,
                           lookback_days=30, skip_days=7)
    signals = {s.symbol: s for s in strat.generate(Panel(panel_data), last_ts)}
    close = panel_data["A"]["close"]
    expected = float(close.iloc[-8] / close.iloc[-38] - 1.0)
    assert signals["A"].meta["momentum"] == pytest.approx(expected, abs=1e-5)


def test_signals_carry_strategy_name(panel_data, last_ts):
    strat = BasketMomentum(universe_size=3, long_leg=1, short_leg=1)
    signals = strat.generate(Panel(panel_data), last_ts)
    assert all(s.meta.get("strategy") == "sepet_momentum" for s in signals)


def test_insufficient_history_returns_no_signal():
    strat = BasketMomentum(universe_size=2, long_leg=1, short_leg=1)
    df = daily_series(10, 100, 110, 5000)
    assert strat.generate(Panel({"A": df}), df.index[-1]) == []


def test_research_candidate_flag():
    """Arastirma adayi kapilara tabi olmali."""
    assert BasketMomentum().research_candidate is True
