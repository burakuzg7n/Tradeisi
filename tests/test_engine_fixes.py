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
    assert t.exit_reason == "stop"
    assert t.exit_price == pytest.approx(110.0)
    assert t.pnl_r < -1.0


def _costly_bt():
    return Backtester(BacktestParams(
        initial_balance=10_000, maker_fee=0.0005, taker_fee=0.001,
        slippage_rate=0.001))


def _expected_pnl(side, size, entry_fill, exit_px, entry_fee_rate, exit_fee_rate):
    gross = (exit_px - entry_fill) * size if side == "long" else (entry_fill - exit_px) * size
    return gross - entry_fill * size * entry_fee_rate - exit_px * size * exit_fee_rate


def test_market_gap_through_stop_costs_are_exact():
    """#3: stopun ötesinde dolan market emir gerçekleşir; PnL ücret+slippage dahil TAM."""
    bars = [
        (101, 102, 100.5, 101),
        (98, 99, 97, 98),      # open=98 <= stop=100
        (98, 99, 97, 98),
    ]
    o = _order(entry=101.0, stop=100.0, target=103.0, created_idx=0, expiry_idx=2)
    bt = _costly_bt()
    r = bt.run(make_df(bars), [o])
    assert len(r.trades) == 1 and r.gap_stopouts == 1
    t = r.trades[0]
    size = 10_000 * bt.p.risk_per_trade / 1.0          # planlanan risk = 1
    fill = 98 * 1.001                                   # giriş: open + slippage
    exit_px = 98 * 0.999                                # çıkış: HAM open - slippage
    assert t.exit_price == pytest.approx(exit_px)
    assert t.pnl_usd == pytest.approx(
        _expected_pnl("long", size, fill, exit_px, 0.001, 0.001))


def test_short_market_gap_through_stop_costs_are_exact():
    bars = [
        (99, 100, 98, 99),
        (110, 111, 109, 110),   # open=110 >= stop=105
        (110, 111, 109, 110),
    ]
    o = _order(side="short", entry=99.0, stop=105.0, target=90.0,
               created_idx=0, expiry_idx=2)
    bt = _costly_bt()
    r = bt.run(make_df(bars), [o])
    assert len(r.trades) == 1 and r.gap_stopouts == 1
    t = r.trades[0]
    size = 10_000 * bt.p.risk_per_trade / 6.0
    fill = 110 * 0.999
    exit_px = 110 * 1.001
    assert t.exit_price == pytest.approx(exit_px)
    assert t.pnl_usd == pytest.approx(
        _expected_pnl("short", size, fill, exit_px, 0.001, 0.001))


def test_limit_gap_through_stop_costs_are_exact():
    """#2 (limit yolu): açılıştan dolum (maker), hemen stop (taker), ücretler tam."""
    bars = [
        (105, 106, 104, 105),
        (90, 92, 89, 91),      # limit 100, stop 95; bar 90'da açıldı
        (91, 92, 90, 91),
    ]
    o = _order(market=False, entry=100.0, stop=95.0, target=110.0,
               created_idx=0, expiry_idx=2, cancel_beyond=-1e18)
    bt = _costly_bt()
    r = bt.run(make_df(bars), [o])
    assert len(r.trades) == 1 and r.gap_stopouts == 1
    t = r.trades[0]
    size = 10_000 * bt.p.risk_per_trade / 5.0
    exit_px = 90 * 0.999
    assert t.entry == pytest.approx(90.0)
    assert t.exit_price == pytest.approx(exit_px)
    assert t.pnl_usd == pytest.approx(
        _expected_pnl("long", size, 90.0, exit_px, 0.0005, 0.001))


def test_market_fill_beyond_target_fills_and_exits_with_costs():
    """#3 (hedef tarafı): iptal YOK; dolar, hemen kapanır, maliyet öder (küçük kayıp)."""
    bars = [
        (100, 101, 99, 100),
        (115, 116, 114, 115),  # open=115 >= target=110
        (115, 116, 114, 115),
    ]
    o = _order(entry=100.0, stop=95.0, target=110.0, created_idx=0, expiry_idx=2)
    bt = _costly_bt()
    r = bt.run(make_df(bars), [o])
    assert len(r.trades) == 1 and r.gap_target_exits == 1
    t = r.trades[0]
    size = 10_000 * bt.p.risk_per_trade / 5.0
    fill = 115 * 1.001
    exit_px = 115 * 0.999
    assert t.exit_reason == "gap_target"
    assert t.pnl_usd == pytest.approx(
        _expected_pnl("long", size, fill, exit_px, 0.001, 0.001))
    assert t.pnl_usd < 0   # maliyetler yüzünden küçük kayıp, bedava kâr değil


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


def test_short_market_fill_beyond_target_costs_are_exact():
    bars = [
        (99, 100, 98, 99),
        (85, 86, 84, 85),      # open=85 <= target=90 (short)
        (85, 86, 84, 85),
    ]
    o = _order(side="short", entry=99.0, stop=105.0, target=90.0,
               created_idx=0, expiry_idx=2)
    bt = _costly_bt()
    r = bt.run(make_df(bars), [o])
    assert len(r.trades) == 1 and r.gap_target_exits == 1
    t = r.trades[0]
    size = 10_000 * bt.p.risk_per_trade / 6.0
    fill = 85 * 0.999
    exit_px = 85 * 1.001
    assert t.exit_reason == "gap_target"
    assert t.pnl_usd == pytest.approx(
        _expected_pnl("short", size, fill, exit_px, 0.001, 0.001))


def test_short_limit_gap_through_stop_costs_are_exact():
    bars = [
        (95, 96, 94, 95),
        (110, 111, 109, 110),  # short limit 100, stop 105; bar 110'da açıldı
        (110, 111, 109, 110),
    ]
    o = _order(side="short", market=False, entry=100.0, stop=105.0, target=90.0,
               created_idx=0, expiry_idx=2, cancel_beyond=1e18)
    bt = _costly_bt()
    r = bt.run(make_df(bars), [o])
    assert len(r.trades) == 1 and r.gap_stopouts == 1
    t = r.trades[0]
    size = 10_000 * bt.p.risk_per_trade / 5.0
    exit_px = 110 * 1.001
    assert t.entry == pytest.approx(110.0)
    assert t.pnl_usd == pytest.approx(
        _expected_pnl("short", size, 110.0, exit_px, 0.0005, 0.001))


def test_short_market_entry_bar_target_touch_is_counted():
    bars = [
        (100, 101, 99, 100),
        (100, 101, 89, 90),    # açılışta short dolar; low 89 <= target 90; high 101 < stop 105
        (90, 91, 89, 90),
    ]
    o = _order(side="short", entry=100.0, stop=105.0, target=90.0,
               created_idx=0, expiry_idx=2)
    r = _bt().run(make_df(bars), [o])
    assert len(r.trades) == 1
    assert r.trades[0].exit_reason == "target"
    assert r.trades[0].exit_idx == 1


def test_short_market_entry_bar_stop_and_target_both_means_stop():
    bars = [
        (100, 101, 99, 100),
        (100, 106, 89, 100),   # hem stop (106>=105) hem hedef (89<=90) -> STOP
        (100, 101, 99, 100),
    ]
    o = _order(side="short", entry=100.0, stop=105.0, target=90.0,
               created_idx=0, expiry_idx=2)
    r = _bt().run(make_df(bars), [o])
    assert r.trades[0].exit_reason == "stop"
