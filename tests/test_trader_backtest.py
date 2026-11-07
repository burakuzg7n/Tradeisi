"""Backtest motoru semantigi — muhafazakar varsayimlarin regresyon testleri."""
from __future__ import annotations

import pandas as pd
import pytest

from trader.backtest import Backtester
from trader.config import CostModel, RiskSettings
from tests.test_trader_helpers import OneShot, flat_ohlcv, make_ohlcv


def bt(**kwargs) -> Backtester:
    params = dict(
        costs=CostModel(maker_fee=0.0, taker_fee=0.0, slippage_rate=0.0),
        risk=RiskSettings(max_gross_leverage=10.0, max_positions=10,
                          max_drawdown_pct=0.99),
        initial_equity=10_000.0,
    )
    params.update(kwargs)
    return Backtester(**params)


# ---------------------------------------------------------------- fill

def test_market_order_fills_at_next_bar_open():
    """Sinyal barinda DEGIL, sonraki barin open'inda dolar (lookahead yok)."""
    df = make_ohlcv([
        (100, 100, 100, 100, 1),   # bar 0: sinyal burada
        (105, 106, 104, 105, 1),   # bar 1: open = 105 -> burada dolar
        (106, 107, 105, 106, 1),
    ])
    strategy = OneShot(index=0)
    result = bt().run({"A": df}, strategy)
    assert len(result.trades) == 1
    assert result.trades[0].entry == 105.0


def test_limit_order_not_filled_without_touch():
    """Limit fiyat dokunulmazsa dolmaz; dokunulunca dolar."""
    class LimitStrategy(OneShot):
        def generate(self, panel, ts):
            from trader.strategy import Signal
            if len(panel.frame("A")) - 1 != 0:
                return []
            return [Signal(symbol="A", side="long", action="open", entry=99.5,
                           stop=95.0, target=110.0, order_type="limit",
                           ts=ts.isoformat(), meta={})]

    df = make_ohlcv([
        (100, 101, 99.8, 100, 1),   # low 99.8 > 99.5 -> dolmaz
        (100, 101, 99.0, 99.2, 1),  # low 99.0 <= 99.5 -> dolar @ 99.5
        (100, 101, 99.0, 99.2, 1),
    ])
    result = bt().run({"A": df}, LimitStrategy(index=0))
    assert len(result.trades) == 1
    assert result.trades[0].entry == pytest.approx(99.5)
    assert result.trades[0].entry_ts == df.index[1]


def test_same_bar_stop_and_target_stop_wins():
    """Ayni barda stop + target -> STOP sayilir (muhafazakar)."""
    df = make_ohlcv([
        (100, 100, 100, 100, 1),
        (100, 110, 90, 100, 1),     # bar 1: open 100, high 110 (target), low 90 (stop)
        (100, 100, 100, 100, 1),
    ])
    strategy = OneShot(index=0, entry=100.0, stop_pct=0.05, target_pct=0.10)
    result = bt().run({"A": df}, strategy)
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.exit_reason == "stop"
    assert trade.exit == 95.0
    assert trade.pnl_usd < 0


def test_gap_through_stop_exits_at_open():
    """Acik pozisyonun sonraki barinda stopun otesinde gap acilirsa
    cikis ACILIS fiyatindan (stop'tan degil) olur."""
    df = make_ohlcv([
        (100, 100, 100, 100, 1),
        (100, 101, 99, 100, 1),     # bar 1: giris 100 (open), stop 95
        (80, 82, 78, 81, 1),        # bar 2: open 80 << stop 95 -> gap
        (81, 82, 80, 81, 1),
    ])
    strategy = OneShot(index=0, entry=100.0, stop_pct=0.05, target_pct=0.50)
    result = bt().run({"A": df}, strategy)
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.exit_reason == "stop"
    assert trade.exit == 80.0        # stop 95 degil, acilis 80
    assert trade.pnl_usd < 0
    assert trade.exit_ts == df.index[2]


def test_fill_beyond_stop_is_immediate_stopout():
    """Dolum fiyati zaten stopun OTESINDEyse aninda stop-out (gap stopout).

    Emir gonderilmis ve dolmus oldugu icin iptal mumkun degildir.
    """
    df = make_ohlcv([
        (100, 100, 100, 100, 1),
        (80, 82, 78, 81, 1),        # bar 1: open 80, stop 95 -> dolum zaten stopun altinda
        (81, 82, 80, 81, 1),
    ])
    strategy = OneShot(index=0, entry=100.0, stop_pct=0.05, target_pct=0.50)
    result = bt().run({"A": df}, strategy)
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.exit_reason == "stop"
    assert trade.entry == 80.0
    assert trade.exit == 80.0
    assert result.gap_stopouts == 1


def test_limit_entry_bar_target_not_counted():
    """Limit giris barinda hedef temasi SAYILMAZ (bar ici sira bilinmez).

    Ayni barda stop vurulursa stop sayilir.
    """
    class LimitStrategy(OneShot):
        def generate(self, panel, ts):
            from trader.strategy import Signal
            if len(panel.frame("A")) - 1 != 0:
                return []
            return [Signal(symbol="A", side="long", action="open", entry=99.0,
                           stop=90.0, target=120.0, order_type="limit",
                           ts=ts.isoformat(), meta={})]

    df = make_ohlcv([
        (100, 100, 100, 100, 1),
        (100, 125, 99, 120, 1),   # low 99 <= 99 (limit dolu), high 125 >= target 120
        (120, 121, 119, 120, 1),  # sonraki bar: limit giris barinda hedef sayilmadi
        (120, 121, 119, 120, 1),
    ])
    result = bt().run({"A": df}, LimitStrategy(index=0))
    assert len(result.trades) == 1
    trade = result.trades[0]
    # giris barinda (bar 1) kapanmadi -> kapanis bar 2'de oldu
    assert trade.entry_ts == df.index[1]
    assert trade.exit_ts >= df.index[2]
    assert trade.exit_reason == "target"


# ---------------------------------------------------------------- ucret

def test_fees_applied_maker_vs_taker():
    costs = CostModel(maker_fee=0.001, taker_fee=0.002, slippage_rate=0.0)
    df = make_ohlcv([
        (100, 100, 100, 100, 1),
        (100, 101, 99, 100, 1),
        (100, 101, 99, 100, 1),
    ])
    strategy = OneShot(index=0, entry=100.0, stop_pct=0.50, target_pct=0.01)
    result = bt(costs=costs).run({"A": df}, strategy)
    trade = result.trades[0]
    # giris 100 (market/taker %0.2) + cikis 101 (target/limit maker %0.1)
    gross = (101 - 100) * trade.qty
    expected_fee = 100 * trade.qty * 0.002 + 101 * trade.qty * 0.001
    assert trade.pnl_usd == pytest.approx(gross - expected_fee)


def test_slippage_always_adverse():
    costs = CostModel(maker_fee=0.0, taker_fee=0.0, slippage_rate=0.001)
    df = make_ohlcv([
        (100, 100, 100, 100, 1),
        (100, 101, 99, 100, 1),
        (100, 101, 99, 100, 1),
    ])
    strategy = OneShot(index=0, entry=100.0, stop_pct=0.50, target_pct=0.01)
    result = bt(costs=costs).run({"A": df}, strategy)
    # long giris: open 100 * (1 + 0.001) = 100.1
    assert result.trades[0].entry == pytest.approx(100.1)


# ---------------------------------------------------------------- funding

def test_funding_long_pays_when_rate_positive():
    costs = CostModel(maker_fee=0.0, taker_fee=0.0, slippage_rate=0.0)
    df = make_ohlcv([
        (100, 100, 100, 100, 1),
        (100, 101, 99, 100, 1),
        (100, 101, 99, 100, 1),
        (100, 101, 99, 100, 1),
    ], start="2023-01-01", freq="8h")
    funding = pd.DataFrame({"funding_rate": [0.001]},
                           index=pd.DatetimeIndex(["2023-01-01 08:00:00"], tz="UTC"))
    # stop 50 / target 150 -> pozisyon butun barlarda acik kalir
    strategy = OneShot(index=0, entry=100.0, stop_pct=0.50, target_pct=0.50)
    result = bt(costs=costs).run({"A": df}, strategy, funding={"A": funding})
    # risk = 10000 * 0.005 = 50; qty = 50 / 50 = 1.0; notional = 100
    # long, pozitif oran odar: -1 * 100 * 0.001 = -0.1
    assert result.funding_paid == pytest.approx(-0.1, abs=1e-6)


def test_funding_with_millisecond_jitter_still_applies():
    """Binance funding zaman damgalari 00:00.002 gibi sapmali gelir; barla
    eslesmezse funding hic uygulanmazdi (regresyon)."""
    costs = CostModel(maker_fee=0.0, taker_fee=0.0, slippage_rate=0.0)
    df = make_ohlcv([
        (100, 100, 100, 100, 1),
        (100, 101, 99, 100, 1),
        (100, 101, 99, 100, 1),
        (100, 101, 99, 100, 1),
    ], start="2023-01-01", freq="8h")
    funding = pd.DataFrame(
        {"funding_rate": [0.001]},
        index=pd.DatetimeIndex(["2023-01-01 08:00:00.002000"], tz="UTC"),
    )
    strategy = OneShot(index=0, entry=100.0, stop_pct=0.50, target_pct=0.50)
    result = bt(costs=costs).run({"A": df}, strategy, funding={"A": funding})
    assert result.funding_paid == pytest.approx(-0.1, abs=1e-6)


def test_multiple_funding_events_in_same_bar_are_summed():
    """Gunluk barda 00/08/16 funding olaylari ayni bara duser -> toplanir."""
    costs = CostModel(maker_fee=0.0, taker_fee=0.0, slippage_rate=0.0)
    df = make_ohlcv([
        (100, 100, 100, 100, 1),
        (100, 101, 99, 100, 1),
        (100, 101, 99, 100, 1),
    ], start="2023-01-01", freq="1D")
    idx = pd.DatetimeIndex(
        ["2023-01-01 00:00:00", "2023-01-01 08:00:00", "2023-01-01 16:00:00"],
        tz="UTC",
    )
    funding = pd.DataFrame({"funding_rate": [0.001, 0.002, 0.003]}, index=idx)
    strategy = OneShot(index=0, entry=100.0, stop_pct=0.50, target_pct=0.50)
    result = bt(costs=costs).run({"A": df}, strategy, funding={"A": funding})
    # toplam oran 0.006 -> long -100 * 0.006 = -0.6
    assert result.funding_paid == pytest.approx(-0.6, abs=1e-6)


def test_funding_after_period_end_is_ignored():
    """Donem bitiminden sonraki funding uygulanmaz."""
    costs = CostModel(maker_fee=0.0, taker_fee=0.0, slippage_rate=0.0)
    df = make_ohlcv([
        (100, 100, 100, 100, 1),
        (100, 101, 99, 100, 1),
    ], start="2023-01-01", freq="1D")
    funding = pd.DataFrame(
        {"funding_rate": [0.001]},
        index=pd.DatetimeIndex(["2023-01-10 00:00:00"], tz="UTC"),
    )
    strategy = OneShot(index=0, entry=100.0, stop_pct=0.50, target_pct=0.50)
    result = bt(costs=costs).run({"A": df}, strategy, funding={"A": funding})
    assert result.funding_paid == pytest.approx(0.0, abs=1e-9)


# ---------------------------------------------------------------- hedef agirlik (mark-to-market)

def test_target_weight_uses_market_value_not_entry_price():
    """Hedef agirlik, mevcut pozisyonun PIYASA degeriyle karsilastirilir.

    Giriş fiyati kullanilsaydi, fiyat yukseldiginde motor gereksiz long alirdi.
    """
    df = make_ohlcv([
        (100, 100, 100, 100, 1),   # bar 0: sinyal
        (100, 100, 100, 100, 1),   # bar 1: giris @100
        (200, 200, 200, 200, 1),   # bar 2: fiyat 200
        (200, 200, 200, 200, 1),   # bar 3: hedef agirligi tekrarla
    ])
    strategy = OneShot(index=0, weight=0.5)
    result = bt(initial_equity=1000.0).run({"A": df}, strategy)
    # 1000 * 0.5 = 500 hedef notional; giris @100 -> 5 adet
    assert result.trades[0].qty == pytest.approx(5.0)
    # fiyat 200'e cikinca 5 adet = 1000 notional; motor hedefi tutturmak icin
    # ALMAMALI (delta ~ 0). Alirsa ilk pozisyon kapanmaz, hacim artar.
    assert len(result.trades) == 1
    assert result.trades[0].qty == pytest.approx(5.0)


def test_kill_switch_reduces_risk_instead_of_freezing_portfolio():
    """Kill switch tetiklenince sinyal uretimi DEVAM eder ama pozisyon
    buyutulmez; portföy dondurulmaz."""
    from trader.strategy import Signal

    class Grow(OneShot):
        name = "grow"
        research_candidate = False
        timeframe = "15m"

        def generate(self, panel, ts):
            sym = list(panel.symbols())[0]
            n = len(panel.frame(sym)) - 1
            if n == 0:
                w = 0.5
            elif n == 2:
                w = 2.0
            else:
                return []
            return [Signal(symbol=sym, side="long", action="target_weight",
                           weight=w, ts=ts.isoformat(), meta={})]

    df = make_ohlcv([
        (100, 100, 100, 100, 1),
        (100, 100, 100, 100, 1),   # giris @100
        (50, 50, 50, 50, 1),       # buyuk dusus -> kill switch
        (50, 50, 50, 50, 1),
    ])
    risk = RiskSettings(max_gross_leverage=10.0, max_positions=10,
                         max_drawdown_pct=0.10)
    strategy = Grow(index=0)
    result = bt(initial_equity=1000.0, risk=risk).run({"A": df}, strategy)
    assert result.kill_switch_triggered is True
    # pozisyon buyutulmedi: hacim 5 adet (500 notional @100) olarak kaldi
    assert result.trades[0].qty == pytest.approx(5.0)
    rejects = [r.get("reject_reason", "") for r in result.rejected_signals]
    assert any("kill switch" in r for r in rejects)


# ---------------------------------------------------------------- hedef agirlik

def test_target_weight_rebalance_creates_delta_orders():
    df = flat_ohlcv(6, price=100.0)
    strategy = OneShot(index=0, weight=0.5)   # equity'nin %50'si long
    result = bt(initial_equity=1000.0).run({"A": df}, strategy)
    # risk_per_trade varsayilan %0.5 -> stop yoksa risk = notional * 0.005
    assert len(result.trades) == 1
    # hedef notional 500, entry 100 -> qty 5
    assert result.trades[0].qty == pytest.approx(5.0)


def test_gross_leverage_cap_applied():
    df = flat_ohlcv(6, price=100.0)
    strategy = OneShot(index=0, weight=5.0)   # %500 iste (cap yoksa)
    risk = RiskSettings(max_gross_leverage=2.0, max_positions=10,
                         max_drawdown_pct=0.99)
    result = bt(initial_equity=1000.0, risk=risk).run({"A": df}, strategy)
    notional = result.trades[0].qty * result.trades[0].entry
    assert notional <= 2.0 * 1000.0 + 1e-6


def test_max_positions_enforced():
    risk = RiskSettings(max_gross_leverage=10.0, max_positions=1,
                         max_drawdown_pct=0.99)
    data = {"A": flat_ohlcv(6, price=100.0), "B": flat_ohlcv(6, price=50.0)}
    from trader.strategy import Signal

    class TwoSymbols(OneShot):
        def generate(self, panel, ts):
            if len(panel.frame("A")) - 1 != 0:
                return []
            return [Signal(symbol=s, side="long", action="target_weight",
                           weight=0.2, ts=ts.isoformat(), meta={})
                    for s in panel.symbols()]

    result = bt(initial_equity=1000.0, risk=risk).run(data, TwoSymbols(index=0))
    assert len(result.trades) == 1


# ---------------------------------------------------------------- lookahead

def test_strategy_never_sees_future_bars():
    df = flat_ohlcv(20, price=100.0)
    strategy = OneShot(index=5)
    result = bt().run({"A": df}, strategy)
    assert strategy.seen_max_ts is not None
    assert strategy.seen_max_ts <= df.index[-1]
    # sinyal 5. barda uretildi -> 6. barda dolmali
    assert result.trades[0].entry_ts == df.index[6]


def test_equity_curve_length_matches_timeline():
    df = flat_ohlcv(10, price=100.0)
    result = bt().run({"A": df}, OneShot(index=0))
    assert len(result.equity_curve) == 10
    assert result.equity_curve.index[0] == df.index[0]


def test_drawdown_kill_switch_stops_new_signals():
    df = make_ohlcv([
        (100, 100, 100, 100, 1),
        (100, 101, 99, 100, 1),
        (90, 91, 89, 90, 1),      # buyuk zarar
        (90, 91, 89, 90, 1),
    ])
    risk = RiskSettings(max_gross_leverage=10.0, max_positions=10,
                         max_drawdown_pct=0.001)
    result = bt(initial_equity=1000.0, risk=risk).run({"A": df}, OneShot(index=0))
    assert result.kill_switch_triggered is True
