"""Plan B portföy motoru: sayısal beklenen sonuçlu sentetik testler.

Gün indeksleri küçük tamsayılar (100, 101, ...). Varsayılan: sinyal yok, düz fiyat.
"""
import math

import pandas as pd
import pytest

from tradebot.portfolio_b import PlanBParams, PortfolioError, run_portfolio

NOCOST = PlanBParams(taker_fee=0.0, slippage_rate=0.0, funding_per_day=0.0)
FULL = PlanBParams()  # gerçek maliyetler: taker 0,055%, slip 0,01%, funding 0,03%/gün


def frame(days, overrides=None, price=100.0):
    """days: gün listesi; overrides: {gün: {sütun: değer}}."""
    overrides = overrides or {}
    rows = []
    for d in days:
        r = dict(open=price, high=price + 1, low=price - 1, close=price,
                 entry_signal=False, exit_signal=False, atr=5.0)
        r.update(overrides.get(d, {}))
        rows.append(r)
    return pd.DataFrame(rows, index=pd.Index(days))


DAYS = list(range(100, 111))


def flat(**kw):
    return {s: frame(DAYS) for s in kw.get("symbols", ("BTCUSDT",))}


def only(trades, sym):
    return [t for t in trades if t.symbol == sym]


# ------------------------------------------------------------------ temel akış
def test_entry_next_open_channel_exit_next_open_no_costs():
    f = {"BTCUSDT": frame(DAYS, {100: dict(entry_signal=True, atr=5.0),
                                 105: dict(exit_signal=True),
                                 106: dict(open=120, high=121, low=119, close=120)})}
    r = run_portfolio(f, 100, 110, NOCOST)
    (t,) = r.trades
    # boyut = 10.000 × 0,005 ÷ (2 × 5) = 5; stop = 100 − 10 = 90
    assert (t.entry_day, t.entry, t.stop, t.qty) == (101, 100.0, 90.0, 5.0)
    assert (t.exit_day, t.exit, t.reason) == (106, 120.0, "channel_exit")
    assert t.pnl == pytest.approx(100.0)
    assert t.pnl_r == pytest.approx(2.0)
    assert r.final_balance == pytest.approx(10_100.0)
    assert r.counters["channel_exits"] == 1


def test_full_costs_exact_pnl():
    f = {"BTCUSDT": frame(DAYS, {100: dict(entry_signal=True, atr=5.0),
                                 105: dict(exit_signal=True),
                                 106: dict(open=120, high=121, low=119, close=120)})}
    r = run_portfolio(f, 100, 110, FULL)
    (t,) = r.trades
    fill = 100 * 1.0001
    qty = 50.0 / 10.0
    exit_px = 120 * (1 - 0.0001)
    entry_fee = fill * qty * 0.00055
    exit_fee = exit_px * qty * 0.00055
    funding = fill * qty * 0.0003 * 6          # 101..106 dahil = 6 gün
    expected = (exit_px - fill) * qty - entry_fee - exit_fee - funding
    assert t.entry == pytest.approx(fill)
    assert t.stop == pytest.approx(fill - 10)
    assert t.funding == pytest.approx(funding)
    assert t.pnl == pytest.approx(expected)
    assert r.final_balance == pytest.approx(10_000 + expected)


def test_entry_day_stop_with_costs():
    f = {"BTCUSDT": frame(DAYS, {100: dict(entry_signal=True, atr=5.0),
                                 101: dict(low=80)})}
    r = run_portfolio(f, 100, 110, FULL)
    (t,) = r.trades
    fill = 100 * 1.0001
    stop = fill - 10
    exit_px = stop * (1 - 0.0001)
    expected = ((exit_px - fill) * 5 - fill * 5 * 0.00055 - exit_px * 5 * 0.00055
                - fill * 5 * 0.0003 * 1)
    assert (t.entry_day, t.exit_day, t.reason) == (101, 101, "stop")
    assert t.exit == pytest.approx(exit_px)
    assert t.pnl == pytest.approx(expected)
    assert r.counters["entry_day_stops"] == 1


def test_entry_day_open_below_stop_fills_at_open():
    # ATR çok küçük: stop = 100,01 − 0,002 > açılış 100 → çıkış açılıştan (stoptan değil)
    f = {"BTCUSDT": frame(DAYS, {100: dict(entry_signal=True, atr=0.001)})}
    r = run_portfolio(f, 100, 110, FULL)
    (t,) = r.trades
    assert t.stop > 100
    assert t.exit == pytest.approx(100 * (1 - 0.0001))


def test_gap_stop_exits_at_open():
    f = {"BTCUSDT": frame(DAYS, {100: dict(entry_signal=True, atr=5.0),
                                 103: dict(open=85, high=86, low=84, close=85)})}
    r = run_portfolio(f, 100, 110, NOCOST)
    (t,) = r.trades
    assert (t.exit_day, t.exit, t.reason) == (103, 85.0, "stop")
    assert t.pnl == pytest.approx((85 - 100) * 5)
    assert r.counters["gap_stops"] == 1


def test_intraday_stop_exits_at_stop():
    f = {"BTCUSDT": frame(DAYS, {100: dict(entry_signal=True, atr=5.0),
                                 103: dict(low=89)})}
    r = run_portfolio(f, 100, 110, NOCOST)
    (t,) = r.trades
    assert (t.exit_day, t.exit) == (103, 90.0)
    assert t.pnl == pytest.approx(-50.0)


# ------------------------------------------------------------------ kontenjan / öncelik
SYMS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT")


def test_priority_order_independent_of_input_order():
    ov = {100: dict(entry_signal=True)}
    f = {s: frame(DAYS, ov) for s in reversed(SYMS)}
    r = run_portfolio(f, 100, 103, NOCOST)
    assert sorted(t.symbol for t in r.trades) == ["BTCUSDT", "ETHUSDT"]
    assert r.counters["entries_cancelled_capacity"] == 2
    assert all(t.reason == "period_end" for t in r.trades)


def _two_open_then(btc_day103, sol_signal_day=102):
    """BTC ve ETH 101'de açılır; SOL sinyali sol_signal_day kapanışında."""
    f = {
        "BTCUSDT": frame(DAYS, {100: dict(entry_signal=True), **btc_day103}),
        "ETHUSDT": frame(DAYS, {100: dict(entry_signal=True)}),
        "SOLUSDT": frame(DAYS, {sol_signal_day: dict(entry_signal=True)}),
    }
    return run_portfolio(f, 100, 110, NOCOST)


def test_gap_stop_slot_not_reusable_same_open():
    r = _two_open_then({103: dict(open=85, high=86, low=84, close=85)})
    assert only(r.trades, "SOLUSDT") == []
    assert r.counters["entries_cancelled_capacity"] == 1


def test_intraday_stop_slot_free_next_day():
    # BTC 102'de gün içi stop; SOL sinyali 102 kapanışı → 103 açılışında girebilir
    r = _two_open_then({102: dict(low=80)}, sol_signal_day=102)
    (sol,) = only(r.trades, "SOLUSDT")
    assert sol.entry_day == 103


def test_gap_stop_slot_free_next_day():
    r = _two_open_then({103: dict(open=85, high=86, low=84, close=85)}, sol_signal_day=103)
    (sol,) = only(r.trades, "SOLUSDT")
    assert sol.entry_day == 104


def test_channel_exit_slot_reusable_same_open():
    r = _two_open_then({102: dict(exit_signal=True)})
    (sol,) = only(r.trades, "SOLUSDT")
    assert sol.entry_day == 103
    btc = only(r.trades, "BTCUSDT")[0]
    assert (btc.exit_day, btc.reason) == (103, "channel_exit")


def test_e11_channel_exit_through_stop_counts_as_channel_exit():
    r = _two_open_then({102: dict(exit_signal=True), 103: dict(open=85, high=86, low=84, close=85)})
    btc = only(r.trades, "BTCUSDT")[0]
    assert (btc.exit_day, btc.exit, btc.reason) == (103, 85.0, "channel_exit")
    assert r.counters["channel_exit_through_stop"] == 1
    assert r.counters["gap_stops"] == 0
    (sol,) = only(r.trades, "SOLUSDT")
    assert sol.entry_day == 103


def test_e11_deferred_channel_exit_through_stop():
    days_btc = [d for d in DAYS if d != 103]          # BTC 103 eksik
    f = {
        "BTCUSDT": frame(days_btc, {100: dict(entry_signal=True), 102: dict(exit_signal=True),
                                    104: dict(open=85, high=86, low=84, close=85)}),
        "ETHUSDT": frame(DAYS, {100: dict(entry_signal=True)}),
        "SOLUSDT": frame(DAYS, {103: dict(entry_signal=True)}),
    }
    r = run_portfolio(f, 100, 110, NOCOST)
    btc = only(r.trades, "BTCUSDT")[0]
    assert (btc.exit_day, btc.exit, btc.reason) == (104, 85.0, "channel_exit")
    assert r.counters["deferred_channel_exits"] == 1
    assert r.counters["channel_exit_through_stop"] == 1
    (sol,) = only(r.trades, "SOLUSDT")
    assert sol.entry_day == 104     # kontenjan aynı açılışta kullanıldı


def test_two_entries_same_open_sized_from_pre_open_balance():
    # BTC 101–103 açık (kâr), 102 çıkış sinyali; ETH ve SOL sinyali 102 → 103 açılışı
    f = {
        "BTCUSDT": frame(DAYS, {100: dict(entry_signal=True), 102: dict(exit_signal=True),
                                103: dict(open=140, high=141, low=139, close=140)}),
        "ETHUSDT": frame(DAYS, {102: dict(entry_signal=True, atr=2.0)}),
        "SOLUSDT": frame(DAYS, {102: dict(entry_signal=True, atr=4.0)}),
    }
    p = PlanBParams(taker_fee=0.0, slippage_rate=0.0, funding_per_day=0.0, max_positions=3)
    r = run_portfolio(f, 100, 110, p)
    btc = only(r.trades, "BTCUSDT")[0]
    assert btc.pnl == pytest.approx(200.0)          # aynı açılışta gerçekleşen kâr
    eth = only(r.trades, "ETHUSDT")[0]
    sol = only(r.trades, "SOLUSDT")[0]
    # ikisi de açılış öncesi bakiye (10.000) ile: risk 50
    assert eth.risk_amount == pytest.approx(50.0) and sol.risk_amount == pytest.approx(50.0)
    assert eth.qty == pytest.approx(50 / 4.0) and sol.qty == pytest.approx(50 / 8.0)


def test_sizing_uses_realized_balance_after_previous_close():
    f = {"BTCUSDT": frame(DAYS, {100: dict(entry_signal=True), 102: dict(exit_signal=True),
                                 103: dict(open=140, high=141, low=139, close=140),
                                 104: dict(entry_signal=True)})}
    r = run_portfolio(f, 100, 110, NOCOST)
    second = r.trades[1]
    assert second.entry_day == 105
    assert second.risk_amount == pytest.approx(10_200 * 0.005)


def test_no_pyramiding():
    f = {"BTCUSDT": frame(DAYS, {100: dict(entry_signal=True), 102: dict(entry_signal=True)})}
    r = run_portfolio(f, 100, 110, NOCOST)
    assert len(r.trades) == 1


def test_invalid_atr_skipped():
    f = {"BTCUSDT": frame(DAYS, {100: dict(entry_signal=True, atr=float("nan"))})}
    r = run_portfolio(f, 100, 110, NOCOST)
    assert r.trades == [] and r.counters["entries_skipped_invalid_atr"] == 1


# ------------------------------------------------------------------ eksik bar (E5b / E12)
def test_pending_entry_cancelled_when_next_bar_missing():
    sol_days = [d for d in DAYS if d != 103]
    f = {"BTCUSDT": frame(DAYS),
         "SOLUSDT": frame(sol_days, {102: dict(entry_signal=True)})}
    r = run_portfolio(f, 100, 110, NOCOST)
    assert r.trades == []
    assert r.counters["entries_cancelled_missing_bar"] == 1


def test_funding_counts_missing_days_and_valuation_uses_last_close():
    btc_days = [d for d in DAYS if d not in (103, 104)]
    f = {"BTCUSDT": frame(btc_days, {100: dict(entry_signal=True),
                                     102: dict(close=110, high=111),
                                     105: dict(exit_signal=True)}),
         "ETHUSDT": frame(DAYS)}
    p = PlanBParams(taker_fee=0.0, slippage_rate=0.0, funding_per_day=0.0003)
    r = run_portfolio(f, 100, 110, p)
    (t,) = r.trades
    assert (t.entry_day, t.exit_day) == (101, 106)
    assert t.funding == pytest.approx(100 * 5 * 0.0003 * 6)
    assert r.missing_day_valuations["BTCUSDT"] == 2
    # 103 günü: BTC barı yok → son kapanış 110 ile değerlenir, funding 3 gün tahakkuk
    assert r.equity.loc[103] == pytest.approx(10_000 + (110 - 100) * 5 - 100 * 5 * 0.0003 * 3)


def test_equity_mtm_includes_entry_fee_and_accrued_funding():
    f = {"BTCUSDT": frame(DAYS, {100: dict(entry_signal=True), 102: dict(close=104)})}
    r = run_portfolio(f, 100, 110, FULL)
    fill = 100 * 1.0001
    qty = 5.0
    exp = 10_000 + (104 - fill) * qty - fill * qty * 0.00055 - fill * qty * 0.0003 * 2
    assert r.equity.loc[102] == pytest.approx(exp)


# ------------------------------------------------------------------ dönem sınırları (E3b / E3c / E13)
def test_period_end_liquidation_with_costs():
    f = {"BTCUSDT": frame(DAYS, {100: dict(entry_signal=True), 110: dict(close=130)})}
    r = run_portfolio(f, 100, 110, FULL)
    (t,) = r.trades
    fill = 100 * 1.0001
    exit_px = 130 * (1 - 0.0001)
    exp = ((exit_px - fill) * 5 - fill * 5 * 0.00055 - exit_px * 5 * 0.00055
           - fill * 5 * 0.0003 * 10)
    assert (t.exit_day, t.reason) == (110, "period_end")
    assert t.pnl == pytest.approx(exp)
    assert r.counters["forced_closes"] == 1
    assert r.final_balance == pytest.approx(10_000 + exp)


def test_period_end_symbol_missing_on_end_day_liquidated_at_last_bar():
    btc_days = [d for d in DAYS if d != 110]
    f = {"BTCUSDT": frame(btc_days, {100: dict(entry_signal=True), 109: dict(close=125)}),
         "ETHUSDT": frame(DAYS)}
    p = PlanBParams(taker_fee=0.0, slippage_rate=0.0, funding_per_day=0.0003)
    r = run_portfolio(f, 100, 110, p)
    (t,) = r.trades
    assert (t.exit_day, t.exit, t.reason) == (109, 125.0, "period_end")
    assert t.funding == pytest.approx(100 * 5 * 0.0003 * 9)   # 101..109


def test_bars_after_end_are_not_used():
    f = {"BTCUSDT": frame(DAYS, {100: dict(entry_signal=True),
                                 106: dict(low=10)})}          # stop 106'da, dönem 105'te biter
    r = run_portfolio(f, 100, 105, NOCOST)
    (t,) = r.trades
    assert (t.exit_day, t.reason) == (105, "period_end")


def test_signals_before_start_do_not_trade():
    f = {"BTCUSDT": frame([99] + DAYS, {99: dict(entry_signal=True)})}
    r = run_portfolio(f, 100, 110, NOCOST)
    assert r.trades == []


def test_no_new_pending_on_end_day():
    f = {"BTCUSDT": frame(DAYS, {110: dict(entry_signal=True)})}
    r = run_portfolio(f, 100, 110, NOCOST)
    assert r.trades == []


def test_metrics_pf_and_dd():
    f = {"BTCUSDT": frame(DAYS, {100: dict(entry_signal=True),
                                 102: dict(low=89),                    # −50
                                 103: dict(entry_signal=True),
                                 105: dict(exit_signal=True),
                                 106: dict(open=130, high=131, low=129, close=130)})}
    r = run_portfolio(f, 100, 110, NOCOST)
    first, second = r.trades
    assert first.pnl == pytest.approx(-50.0)
    # ikinci işlem: risk = 9.950 × 0,005 = 49,75; miktar 4,975; 100 → 130
    assert second.qty == pytest.approx(4.975)
    assert second.pnl == pytest.approx(4.975 * 30)
    assert r.profit_factor == pytest.approx(4.975 * 30 / 50)
    assert r.max_drawdown == pytest.approx(50 / 10_000)
    assert r.final_balance == pytest.approx(9_950 + 4.975 * 30)


def test_validation():
    with pytest.raises(PortfolioError):
        run_portfolio({"XRPUSDT": frame(DAYS)}, 100, 110)
    with pytest.raises(PortfolioError):
        run_portfolio({"BTCUSDT": frame(DAYS).drop(columns=["atr"])}, 100, 110)


def test_pending_entry_cancelled_when_no_symbol_trades_next_day():
    """Takvimde 103 hiç yok (hiçbir sembolün barı yok): 102 sinyali 104'e taşınmaz."""
    days = [d for d in DAYS if d != 103]
    f = {"BTCUSDT": frame(days), "SOLUSDT": frame(days, {102: dict(entry_signal=True)})}
    r = run_portfolio(f, 100, 110, NOCOST)
    assert r.trades == []
    assert r.counters["entries_cancelled_missing_bar"] == 1


# ------------------------------------------------------------------ PR #7 denetimi
def test_e13_liquidation_happens_on_last_bar_and_frees_slot():
    """BTC son barı 107, ortak bitiş 110. BTC 107 kapanışında kapanmalı; SOL'un 108
    sinyali 109'da boş kontenjana girebilmeli; 108'den sonra equity BTC'yi içermemeli."""
    btc_days = [d for d in DAYS if d <= 107]
    f = {
        "BTCUSDT": frame(btc_days, {100: dict(entry_signal=True), 107: dict(close=120)}),
        "ETHUSDT": frame(DAYS, {100: dict(entry_signal=True)}),
        "SOLUSDT": frame(DAYS, {108: dict(entry_signal=True)}),
    }
    r = run_portfolio(f, 100, 110, NOCOST)
    btc = only(r.trades, "BTCUSDT")[0]
    assert (btc.exit_day, btc.exit, btc.reason) == (107, 120.0, "period_end")
    (sol,) = only(r.trades, "SOLUSDT")
    assert sol.entry_day == 109
    assert r.counters["entries_cancelled_capacity"] == 0
    # 108: gerçekleşmiş bakiye 10.100 + ETH (düz) → 10.100
    assert r.equity.loc[107] == pytest.approx(10_100.0)
    assert r.equity.loc[108] == pytest.approx(10_100.0)
    assert r.missing_day_valuations["BTCUSDT"] == 0


def test_last_bar_emits_no_new_orders():
    btc_days = [d for d in DAYS if d <= 107]
    f = {"BTCUSDT": frame(btc_days, {107: dict(entry_signal=True)}), "ETHUSDT": frame(DAYS)}
    r = run_portfolio(f, 100, 110, NOCOST)
    assert r.trades == [] and r.counters["entries_cancelled_missing_bar"] == 0


def test_e16_no_entries_after_capital_exhausted_and_never_negative_qty():
    # ATR çok küçük → dev miktar; 102'de gap −%40 → bakiye eksiye düşer
    f = {"BTCUSDT": frame(DAYS, {100: dict(entry_signal=True, atr=0.0001),
                                 101: dict(low=100),          # giriş günü stopa değmez
                                 102: dict(open=60, high=61, low=59, close=60),
                                 103: dict(entry_signal=True, atr=5.0)}),
         "ETHUSDT": frame(DAYS, {104: dict(entry_signal=True, atr=5.0)})}
    r = run_portfolio(f, 100, 110, NOCOST)
    (t,) = r.trades
    assert t.pnl == pytest.approx((60 - 100) * 50 / 0.0002)
    assert r.final_balance < 0
    assert r.counters["entries_blocked_no_capital"] == 2
    assert all(x.qty > 0 for x in r.trades)


def test_e16_zero_balance_blocks():
    # tam olarak 0'a düşüren kayıp: risk 50, miktar 50/(2·atr); gap ile kayıp = 10.000
    atr = 0.025                                   # miktar = 50 / 0,05 = 1.000
    f = {"BTCUSDT": frame(DAYS, {100: dict(entry_signal=True, atr=atr),
                                 101: dict(low=100),
                                 102: dict(open=90, high=91, low=89, close=90),
                                 103: dict(entry_signal=True, atr=5.0)})}
    r = run_portfolio(f, 100, 110, NOCOST)
    assert r.trades[0].pnl == pytest.approx(-10_000.0)
    assert r.counters["entries_blocked_no_capital"] == 1
    assert len(r.trades) == 1
