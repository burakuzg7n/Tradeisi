import pytest

from tests.conftest import make_df, synthetic_trend_df
from tradebot.backtest import Backtester, monte_carlo_dd
from tradebot.config import BacktestParams, StrategyParams
from tradebot.strategy import PendingOrder, generate_orders


def _order(**kw):
    base = dict(
        side="long", entry=100.0, stop=99.0, target=102.0,
        created_idx=0, expiry_idx=100, cancel_beyond=98.0, meta={},
    )
    base.update(kw)
    return PendingOrder(**base)


def _params():
    return BacktestParams(
        initial_balance=10_000, maker_fee=0.0, taker_fee=0.0, slippage_rate=0.0
    )


def test_limit_fill_then_target():
    bars = [
        (105, 106, 104, 105),   # bar0: emir bu barın kapanışında kurulur
        (105, 105, 100, 101),   # bar1: low=100 → fill @100
        (101, 103, 100.5, 102), # bar2
        (102, 102.5, 101, 102), # bar3
        (102, 103, 101.5, 102), # bar4: high=103 > target=102 → TP (bar2'de zaten)
    ]
    df = make_df(bars)
    r = Backtester(_params()).run(df, [_order()])
    assert len(r.trades) == 1
    t = r.trades[0]
    assert t.exit_reason == "target"
    # risk 1$, RR 2 → +2R; fee=0 → pnl_r ≈ 2
    assert t.pnl_r == pytest.approx(2.0, abs=0.01)


def test_same_bar_fill_and_stop_is_conservative_loss():
    bars = [
        (105, 106, 104, 105),
        (105, 105, 98, 104),    # low=98 → hem entry(100) hem stop(99) → STOP
    ]
    df = make_df(bars)
    r = Backtester(_params()).run(df, [_order()])
    assert len(r.trades) == 1
    assert r.trades[0].exit_reason == "stop"
    assert r.trades[0].pnl_r == pytest.approx(-1.0, abs=0.01)


def test_same_bar_stop_and_target_counts_stop():
    bars = [
        (105, 106, 104, 105),
        (105, 105, 100, 101),          # fill @100
        (101, 103, 98, 99),            # hem stop hem target → STOP
    ]
    df = make_df(bars)
    r = Backtester(_params()).run(df, [_order()])
    assert r.trades[0].exit_reason == "stop"


def test_fill_through_fvg_counts_as_stop_not_cancel():
    """Fiyat FVG'yi delip geçerse limit dolar ve stop yenir — iptal DEĞİL.

    Muhafazakârlık: gerçekleşecek kayıp işlem 'iptal' diye atlanamaz.
    """
    bars = [
        (105, 106, 104, 105),
        (105, 105, 96.5, 97),   # low=96.5: entry(100) + stop(99) aynı barda → STOP
    ]
    df = make_df(bars)
    r = Backtester(_params()).run(df, [_order()])
    assert len(r.trades) == 1
    assert r.trades[0].exit_reason == "stop"
    assert r.cancelled_orders == 0


def test_blocked_order_cancelled_when_position_open():
    """Tek pozisyon kuralı: pozisyon açıkken fill isteyen ikinci emir iptal."""
    bars = [
        (105, 106, 104, 105),
        (105, 105, 100, 101),   # A fill @100; B (100.5) de dolmak ister → iptal
        (101, 101.5, 100.8, 101),
    ]
    df = make_df(bars)
    orders = [
        _order(),
        _order(entry=100.5, stop=99.5, target=102.5, cancel_beyond=98.0),
    ]
    r = Backtester(_params()).run(df, orders)
    assert r.cancelled_orders == 1


def test_order_expiry():
    bars = [(105, 106, 104, 105)] * 5
    df = make_df(bars)
    r = Backtester(_params()).run(df, [_order(expiry_idx=2)])
    assert r.expired_orders == 1
    assert len(r.trades) == 0


def test_fees_reduce_pnl():
    bars = [
        (105, 106, 104, 105),
        (105, 105, 100, 101),
        (101, 103, 101, 102.5),
    ]
    df = make_df(bars)
    no_fee = Backtester(_params()).run(df, [_order()])
    with_fee = Backtester(
        BacktestParams(
            initial_balance=10_000, maker_fee=0.001, taker_fee=0.002,
            slippage_rate=0.0,
        )
    ).run(df, [_order()])
    assert with_fee.trades[0].pnl_usd < no_fee.trades[0].pnl_usd


def test_single_position_rule():
    bars = [
        (105, 106, 104, 105),
        (105, 105, 100, 101),   # her iki emir de fill isterdi
        (101, 101.5, 100.5, 101),
        (101, 105, 101, 104),
    ]
    df = make_df(bars)
    orders = [_order(), _order(entry=100.5, stop=99.5, target=102.5, cancel_beyond=98.0)]
    r = Backtester(_params()).run(df, orders)
    assert len(r.trades) + (1 if r.trades else 0) <= 2
    # aynı anda en fazla 1 pozisyon: ikinci emir ya iptal ya beklemede kaldı
    assert len(r.trades) <= 1


def test_full_pipeline_on_synthetic_data():
    """Motor + strateji uçtan uca sentetik veride hatasız çalışmalı."""
    ltf = synthetic_trend_df(4000)
    htf = ltf.resample("4h").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna()
    params = StrategyParams(use_session_filter=False)
    orders = generate_orders(ltf, htf, params)
    r = Backtester(BacktestParams()).run(ltf, orders)
    s = r.summary()
    assert s["total_trades"] + s["cancelled_orders"] + s["expired_orders"] >= 0
    assert r.equity_curve is not None and len(r.equity_curve) == len(ltf)
    # Equity asla NaN olmamalı
    assert not r.equity_curve.isna().any()


def test_monte_carlo():
    mc = monte_carlo_dd([2.0, -1.0, -1.0, 2.0, -1.0, 2.0] * 20)
    assert mc["p95_dd_r"] > 0


def test_save_load_roundtrip_preserves_dates_with_ms_index(tmp_path):
    """Yeni pandas'ta (unit-koruyan) save_csv tarihleri 1970'e cokertmemeli.

    Burak'in makinesinde yakalanan gercek bug: to_datetime(unit='ms') ->
    datetime64[ms] index -> view('int64')//10**6 -> tum tarihler 1970.
    """
    import pandas as pd
    from tradebot.data import save_csv, load_csv

    idx = pd.date_range("2024-06-01", periods=10, freq="15min", tz="UTC")
    try:
        idx = idx.as_unit("ms")  # bug'i tetikleyen kosulu zorla
    except AttributeError:
        pass
    df = pd.DataFrame(
        {"open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 3.0},
        index=idx,
    )
    p = tmp_path / "t.csv"
    save_csv(df, p)
    back = load_csv(p)
    assert back.index[0].year == 2024, "tarihler 1970'e cokmus - save_csv bug'i"
    assert len(back) == 10


def test_v2_generates_market_order_after_choch():
    """V2: sweep -> tetik seviyesi close ile kirilinca MARKET emir."""
    from tests.test_strategy_server import _bull_scenario_df, _bull_htf
    from tradebot.strategy_v2 import generate_orders_v2
    ltf = _bull_scenario_df()
    htf = _bull_htf()
    params = StrategyParams(ltf_pivot=3, use_session_filter=False)
    orders = generate_orders_v2(ltf, htf, params)
    assert len(orders) >= 1
    o = orders[0]
    assert o.market and o.side == "long"
    assert o.stop < 94.7  # sweep dibi (94) alti
    assert (o.target - o.entry) == pytest.approx(2 * (o.entry - o.stop), rel=0.01)


def test_market_order_fills_at_next_open_with_slippage():
    bars = [
        (105, 106, 104, 105),   # emir bu barin kapanisinda
        (104, 108, 103.5, 107), # open=104'te taker fill
        (107, 112, 106, 111),
    ]
    df = make_df(bars)
    o = _order(market=True, entry=105.0, stop=100.0, target=110.0, expiry_idx=2)
    r = Backtester(BacktestParams(initial_balance=10_000, maker_fee=0.0,
                                  taker_fee=0.0, slippage_rate=0.0)).run(df, [o])
    assert len(r.trades) == 1
    t = r.trades[0]
    assert t.exit_reason == "target"
    # gross = (110-104)*size, risk_amount=50, size=50/(104-100)=12.5 -> pnl=75 -> 1.5R
    assert t.pnl_r == pytest.approx(1.5, abs=0.01)
