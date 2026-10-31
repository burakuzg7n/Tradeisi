"""Motor düzeltmeleri (ChatGPT denetimi #1, #2, #3, #12) — regresyon testleri."""
import pytest

from tests.conftest import make_df
from tradebot.backtest import Backtester
from tradebot.config import BacktestParams
from tradebot.strategy import PendingOrder


def _order(**kw):
    base = dict(
        side="long", entry=100.0, stop=95.0, target=120.0,
        created_idx=0, expiry_idx=100, cancel_beyond=-1e18,
        market=True, meta={},
    )
    base.update(kw)
    return PendingOrder(**base)


def _bt():
    return Backtester(BacktestParams(
        initial_balance=10_000, maker_fee=0.0, taker_fee=0.0, slippage_rate=0.0
    ))


def test_no_same_bar_refill_after_exit():
    """#1: A pozisyonu bar 2 içinde stop olur; B emri bar 2 açılışında DOLMAMALI
    (barın başında A hâlâ açıktı)."""
    bars = [
        (100, 101, 99, 100),   # bar0: A kurulur
        (100, 101, 99, 100),   # bar1: A açılışta dolar; B kurulur (bar1 kapanışı)
        (100, 101, 94, 96),    # bar2: A stop (low 94 <= 95)
        (96, 97, 95.5, 96.5),  # bar3
    ]
    a = _order(created_idx=0, expiry_idx=2)
    b = _order(created_idx=1, expiry_idx=3)
    r = _bt().run(make_df(bars), [a, b])
    assert len(r.trades) == 1, "B aynı barda yer açılmış gibi dolmamalı"
    assert r.cancelled_orders >= 1


def test_stop_gap_exits_at_open_not_at_stop():
    """#2: bar stopun çok altında açılırsa çıkış açılış fiyatından olmalı."""
    bars = [
        (100, 101, 99, 100),   # bar0: emir kurulur
        (100, 101, 99, 100),   # bar1: dolar @100
        (90, 92, 89, 91),      # bar2: gap down, open=90 < stop=95
    ]
    r = _bt().run(make_df(bars), [_order(created_idx=0, expiry_idx=2)])
    t = r.trades[0]
    assert t.exit_reason == "stop"
    assert t.exit_price == pytest.approx(90.0)
    assert t.pnl_r < -1.0   # gap -1R'den fazla kaybettirir


def test_short_stop_gap_exits_at_open():
    bars = [
        (100, 101, 99, 100),
        (100, 101, 99, 100),
        (110, 112, 109, 111),  # gap up, open=110 > stop=105
    ]
    o = _order(side="short", stop=105.0, target=80.0, created_idx=0, expiry_idx=2)
    r = _bt().run(make_df(bars), [o])
    t = r.trades[0]
    assert t.exit_price == pytest.approx(110.0)
    assert t.pnl_r < -1.0


def test_invalid_geometry_order_rejected():
    """#3: dolum fiyatı stopun yanlış tarafındaysa emir reddedilir, sahte kâr yok."""
    bars = [
        (101, 102, 100.5, 101),
        (98, 99, 97, 98),      # open=98 <= stop=100 -> geometri bozuk
        (98, 99, 97, 98),
    ]
    o = _order(entry=101.0, stop=100.0, target=103.0, created_idx=0, expiry_idx=2)
    r = _bt().run(make_df(bars), [o])
    assert len(r.trades) == 0
    assert r.invalid_geometry_orders == 1


def test_trade_entry_is_real_fill_price():
    """#12: ClosedTrade.entry gerçek dolum; sinyal fiyatı meta'da."""
    bars = [
        (105, 106, 104, 105),
        (104, 108, 103.5, 107),   # open=104'te dolar
        (107, 112, 106, 111),
    ]
    o = _order(entry=105.0, stop=100.0, target=110.0, created_idx=0, expiry_idx=2)
    r = _bt().run(make_df(bars), [o])
    t = r.trades[0]
    assert t.entry == pytest.approx(104.0)
    assert t.meta["signal_entry"] == 105.0
