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


def test_market_gap_through_stop_is_costly_loss_not_free_cancel():
    """#3 (revize): stopun ötesinde dolan market emir GERÇEKLEŞİR ve hemen stop olur."""
    bars = [
        (101, 102, 100.5, 101),
        (98, 99, 97, 98),      # open=98 <= stop=100 -> gap through stop
        (98, 99, 97, 98),
    ]
    o = _order(entry=101.0, stop=100.0, target=103.0, created_idx=0, expiry_idx=2)
    r = Backtester(BacktestParams(initial_balance=10_000, maker_fee=0.0005,
                                  taker_fee=0.001, slippage_rate=0.001)).run(
        make_df(bars), [o])
    assert len(r.trades) == 1, "iptal edilmemeli, maliyetli kayıp yazılmalı"
    t = r.trades[0]
    assert t.exit_reason == "stop"
    assert t.pnl_usd < 0
    assert r.gap_stopouts == 1


def test_limit_gap_through_stop_fills_at_open_and_stops():
    """#2 (limit yolu): limit emir stopun ötesinde AÇILAN barda dolar ve stop olur."""
    bars = [
        (105, 106, 104, 105),
        (90, 92, 89, 91),      # limit 100, stop 95; bar 90'da açıldı
        (91, 92, 90, 91),
    ]
    o = _order(market=False, entry=100.0, stop=95.0, target=110.0,
               created_idx=0, expiry_idx=2, cancel_beyond=-1e18)
    r = _bt().run(make_df(bars), [o])
    assert len(r.trades) == 1
    t = r.trades[0]
    assert t.entry == pytest.approx(90.0)          # gerçek dolum = açılış
    assert t.exit_price == pytest.approx(90.0)     # stop 95'ten DEĞİL açılıştan
    assert r.gap_stopouts == 1


def test_market_fill_beyond_target_is_skipped():
    """#3 (hedef tarafı): dolum hedefin ötesindeyse işlem alınmaz."""
    bars = [
        (100, 101, 99, 100),
        (115, 116, 114, 115),  # open=115 >= target=110
        (115, 116, 114, 115),
    ]
    o = _order(entry=100.0, stop=95.0, target=110.0, created_idx=0, expiry_idx=2)
    r = _bt().run(make_df(bars), [o])
    assert len(r.trades) == 0
    assert r.invalid_geometry_orders == 1


def test_market_entry_bar_target_touch_is_counted():
    """#4: market emir açılışta dolar; stop yok, hedef teması aynı barda işlenir."""
    bars = [
        (100, 101, 99, 100),
        (100, 112, 99.5, 111),   # açılışta dolar; high 112 >= target 110; low 99.5 > stop 95
        (111, 112, 110, 111),
    ]
    o = _order(entry=100.0, stop=95.0, target=110.0, created_idx=0, expiry_idx=2)
    r = _bt().run(make_df(bars), [o])
    assert len(r.trades) == 1
    assert r.trades[0].exit_reason == "target"
    assert r.trades[0].exit_idx == 1


def test_market_entry_bar_stop_and_target_both_means_stop():
    bars = [
        (100, 101, 99, 100),
        (100, 112, 94, 100),     # hem stop (94<=95) hem hedef (112>=110) -> STOP
        (100, 101, 99, 100),
    ]
    o = _order(entry=100.0, stop=95.0, target=110.0, created_idx=0, expiry_idx=2)
    r = _bt().run(make_df(bars), [o])
    assert r.trades[0].exit_reason == "stop"


def test_gap_stop_with_slippage_direction():
    """Slippage açıkken gap stop açılıştan ALEYHE slippage ile çıkar (long: aşağı)."""
    bars = [
        (100, 101, 99, 100),
        (100, 101, 99, 100),
        (90, 92, 89, 91),
    ]
    bt = Backtester(BacktestParams(initial_balance=10_000, maker_fee=0.0,
                                   taker_fee=0.0, slippage_rate=0.001))
    r = bt.run(make_df(bars), [_order(created_idx=0, expiry_idx=2)])
    assert r.trades[0].exit_price == pytest.approx(90.0 * 0.999)


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
