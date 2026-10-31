"""V2 protokolü: tek atış kilidi, dönem kesme/ısınma, birleşik metrikler, tasfiye,
V2 lookahead testi (ChatGPT #11)."""
import json
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from tests.conftest import make_df, synthetic_trend_df
from tradebot import protocol_v2 as P
from tradebot.backtest import Backtester, BacktestResult, ClosedTrade
from tradebot.config import BacktestParams, StrategyParams
from tradebot.data import save_csv
from tradebot.strategy import PendingOrder
from tradebot.strategy_v2 import generate_orders_v2

SP = StrategyParams(use_session_filter=False)
PER = P.Periods(insample_start="2025-01-01", insample_end_excl="2025-02-01",
                holdout_start="2025-02-01")


def _htf_from(ltf: pd.DataFrame) -> pd.DataFrame:
    return ltf.resample("4h").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna()


def _write_data(d, symbols=("AAA", "BBB"), n=6000, seeds=(7, 11)):
    for s, seed in zip(symbols, seeds):
        ltf = synthetic_trend_df(n=n, seed=seed)
        save_csv(ltf, d / f"{s}_15m.csv")
        save_csv(_htf_from(ltf), d / f"{s}_4h.csv")


def _order(**kw):
    base = dict(side="long", entry=100.0, stop=95.0, target=120.0, created_idx=0,
                expiry_idx=2, cancel_beyond=-1e18, market=True, meta={})
    base.update(kw)
    return PendingOrder(**base)


# ------------------------------------------------------------- lookahead (V2)
def _cut_inputs(ltf, htf, k):
    """k bara kadar LTF; o ana KADAR KAPANMIŞ HTF mumları (kısmi mum yok)."""
    last_ts = ltf.index[k - 1]
    return ltf.iloc[:k], htf[htf.index + pd.Timedelta("4h") <= last_ts]


def _sig(orders):
    return [(o.side, o.created_idx, o.entry, o.stop, o.target) for o in orders]


def test_v2_orders_do_not_depend_on_future_bars():
    """Veriyi k barda kes: k'dan ÖNCE oluşan emir listesi, tam verideki listenin
    AYNISI olmalı (ne eksik ne fazla). Kesim noktaları her emrin sweep'inin hemen
    ardından ve emir barında seçilir: gelecek barlara bakan her sızıntı (sweep
    penceresi, tetik seviyesi, bias) buradan geçemez."""
    ltf = synthetic_trend_df(n=6000, seed=7)
    htf = _htf_from(ltf)
    full = generate_orders_v2(ltf, htf, SP)
    assert len(full) >= 10, "sentetik veri yeterli V2 emri üretmeli; test anlamsız kalmasın"
    cuts = set()
    for o in full[:14]:
        s_idx = o.meta["sweep_idx"]
        cuts.update(range(s_idx + 2, s_idx + 9))          # sweep'ten hemen sonra
        cuts.update({o.created_idx, o.created_idx + 1})   # emir barı ve bir önceki
    for k in sorted(c for c in cuts if 300 < c < len(ltf)):
        l, h = _cut_inputs(ltf, htf, k)
        want = _sig([x for x in full if x.created_idx < k])
        got = _sig(generate_orders_v2(l, h, SP))
        assert got == want, f"k={k}: kesilmiş veri farklı emir üretti → gelecek sızıntısı"


def test_htf_bias_has_no_lookahead():
    """Bias'ı doğrudan sına: LTF barı k'ya kadar KAPANMIŞ HTF mumlarıyla hesaplanan
    bias, tam veriyle hesaplananın aynı öneki olmalı (kapanmamış 4H mum kullanılmaz)."""
    from tradebot.structure import htf_bias_for_ltf
    ltf = synthetic_trend_df(n=6000, seed=7)
    htf = _htf_from(ltf)
    full = htf_bias_for_ltf(ltf.index, htf, "4h", SP.htf_pivot)
    assert len(set(full.tolist())) >= 2, "bias değişmeli; test anlamsız kalmasın"
    for k in range(200, len(ltf), 13):               # 4h sınırına hizalı olmayan kesimler
        l, h = _cut_inputs(ltf, htf, k)
        part = htf_bias_for_ltf(l.index, h, "4h", SP.htf_pivot)
        assert np.array_equal(part, full[:k]), f"k={k}: bias gelecek HTF mumuna bağımlı"


# ------------------------------------------------------------- dönem dilimleme
def test_run_period_uses_warmup_but_only_period_orders():
    ltf = synthetic_trend_df(n=6000, seed=7)
    htf = _htf_from(ltf)
    start = ltf.index[2000]
    res, info = P.run_period(ltf, htf, start.isoformat(), ltf.index[4800], SP, BacktestParams())
    assert info["period_first_bar"] == str(start)
    assert info["orders_in_period"] <= info["orders_total_incl_warmup"]
    # dönem sonrası veri kullanılmaz: son bar end'den önce
    assert pd.Timestamp(info["period_last_bar"]) < ltf.index[4800]
    # kesilmiş veriyle aynı emirler (kesme gerçekten uygulandı)
    cut_orders = generate_orders_v2(ltf[ltf.index < ltf.index[4800]],
                                    htf[htf.index < ltf.index[4800]], SP)
    assert info["orders_total_incl_warmup"] == len(cut_orders)


# ------------------------------------------------------------- tasfiye (E3b)
def _bt_costly():
    return Backtester(BacktestParams(initial_balance=10_000, maker_fee=0.0005,
                                     taker_fee=0.001, slippage_rate=0.001))


def test_liquidate_at_end_closes_open_position_with_costs():
    bars = [(100, 101, 99, 100), (100, 101, 99, 100), (100, 101, 99, 100.5)]
    df = make_df(bars)
    bt = _bt_costly()
    r_off = bt.run(df, [_order()])
    assert len(r_off.trades) == 0                       # tasfiyesiz: açık kalır
    r = bt.run(df, [_order()], liquidate_at_end=True)
    assert len(r.trades) == 1 and r.forced_closes == 1
    t = r.trades[0]
    assert t.exit_reason == "period_end"
    size = 10_000 * bt.p.risk_per_trade / (100 * 1.001 - 95)   # gerçek dolum riski
    fill = 100 * 1.001
    exit_px = 100.5 * 0.999
    pnl = (exit_px - fill) * size - fill * size * 0.001 - exit_px * size * 0.001
    assert t.exit_price == pytest.approx(exit_px)
    assert t.pnl_usd == pytest.approx(pnl)
    assert float(r.equity_curve.iloc[-1]) == pytest.approx(10_000 + pnl)


# ------------------------------------------------------------- birleşik metrikler (E3)
def _trade(pnl, year=2024):
    return ClosedTrade(side="long", entry=1, stop=0.9, target=1.2, exit_price=1,
                       exit_reason="target", entry_idx=0, exit_idx=1, pnl_usd=pnl,
                       pnl_r=pnl / 50, risk_amount=50, position_size=1,
                       meta={"timestamp": f"{year}-03-01 08:00:00+00:00"})


def _result(pnls, eq):
    idx = pd.date_range("2024-01-01", periods=len(eq), freq="15min", tz="UTC")
    r = BacktestResult()
    r.trades = [_trade(p) for p in pnls]
    r.equity_curve = pd.Series(eq, index=idx)
    return r


def test_combine_net_pf_and_dd_on_summed_equity():
    a = _result([300, -100], [10_000, 10_300, 10_200, 10_200])
    b = _result([-200, 100], [10_000, 9_800, 9_800, 9_900])
    c = P.combine({"A": a, "B": b}, 10_000)
    assert c["total_trades"] == 4
    assert c["profit_factor"] == pytest.approx((300 + 100) / (100 + 200))
    total = np.array([20_000, 20_100, 20_000, 20_100])
    peak = np.maximum.accumulate(total)
    assert c["max_drawdown"] == pytest.approx(((peak - total) / peak).max())


def test_combine_pads_late_starting_symbol_with_initial_balance():
    a = _result([10], [10_000, 10_010, 10_010, 10_010])
    b = _result([0], [10_000, 10_000])
    b.equity_curve.index = a.equity_curve.index[2:]     # B ikinci yarıda başlar
    c = P.combine({"A": a, "B": b}, 10_000)
    assert c["final_total"] == pytest.approx(20_010)


def test_gate_boundaries_are_strict_as_spec():
    ok = {"profit_factor": 1.31, "total_trades": 150, "max_drawdown": 0.149}
    assert P.evaluate_insample(ok)["passed"]
    assert not P.evaluate_insample({**ok, "profit_factor": 1.3})["passed"]      # > strict
    assert not P.evaluate_insample({**ok, "total_trades": 149})["passed"]
    assert not P.evaluate_insample({**ok, "max_drawdown": 0.15})["passed"]      # < strict
    assert P.evaluate_insample({**ok, "profit_factor": float("inf")})["passed"]
    ho = {"profit_factor": 1.16, "max_drawdown": 0.10, "total_trades": 5}
    assert P.evaluate_holdout(ho)["passed"]                      # işlem sayısı kapı değil
    assert not P.evaluate_holdout({**ho, "profit_factor": 1.15})["passed"]


# ------------------------------------------------------------- veri yardımcıları
def test_last_full_day_end_and_missing_bars():
    full = make_df([(1, 1, 1, 1)] * 96, start="2026-01-01")            # tam 1 gün
    assert P.last_full_day_end(full) == pd.Timestamp("2026-01-02", tz="UTC")
    part = make_df([(1, 1, 1, 1)] * 100, start="2026-01-01")           # +4 bar kısmi gün
    assert P.last_full_day_end(part) == pd.Timestamp("2026-01-02", tz="UTC")
    gap = make_df([(1, 1, 1, 1)] * 10, start="2026-01-01").drop(
        pd.Timestamp("2026-01-01 00:45", tz="UTC"))
    assert P.data_report(gap, "15min")["missing_bars"] == 1
    multi = make_df([(1, 1, 1, 1)] * 20, start="2026-01-01").drop(
        [pd.Timestamp(f"2026-01-01 0{h}:{m}", tz="UTC")
         for h, m in ((1, "00"), (1, "15"), (1, "30"), (3, "00"))])
    rep = P.data_report(multi, "15min")
    assert (rep["missing_bars"], rep["gap_count"], rep["max_gap_bars"]) == (4, 2, 3)
    assert rep["gaps"][0] == {"start": "2026-01-01 01:00:00+00:00", "bars": 3}


# ------------------------------------------------------------- TEK ATIŞ kilidi
def test_single_shot_lock_and_holdout_gating(tmp_path):
    data, rep = tmp_path / "data", tmp_path / "reports"
    data.mkdir()
    _write_data(data)
    kw = dict(data_dir=data, report_dir=rep, symbols=("AAA", "BBB"), periods=PER, sp=SP)

    r = P.run_protocol("insample", **kw)
    assert (rep / P.INSAMPLE_FILE).exists() and (rep / "V2_INSAMPLE.md").exists()
    assert r["period"]["end_exclusive"].startswith("2025-02-01")
    json.loads((rep / P.INSAMPLE_FILE).read_text(encoding="utf-8"))   # geçerli JSON

    with pytest.raises(P.ProtocolError, match="TEK ATIŞ"):
        P.run_protocol("insample", **kw)

    # in-sample KALDI ise hold-out reddedilir
    ins = json.loads((rep / P.INSAMPLE_FILE).read_text(encoding="utf-8"))
    ins["gates_passed"] = False
    (rep / P.INSAMPLE_FILE).write_text(json.dumps(ins), encoding="utf-8")
    with pytest.raises(P.ProtocolError, match="REDDEDİLDİ"):
        P.run_protocol("holdout", **kw)

    # GEÇTİ ama kod parmak izi farklıysa reddedilir
    ins["gates_passed"] = True
    ins["code_fingerprint"] = "0" * 64
    (rep / P.INSAMPLE_FILE).write_text(json.dumps(ins), encoding="utf-8")
    with pytest.raises(P.ProtocolError, match="parmak izi"):
        P.run_protocol("holdout", **kw)

    # her şey tutarlıysa hold-out koşar, sonra kilitlenir
    ins["code_fingerprint"] = P.code_fingerprint()
    (rep / P.INSAMPLE_FILE).write_text(json.dumps(ins), encoding="utf-8")
    ho = P.run_protocol("holdout", **kw)
    assert ho["phase"] == "holdout" and ho["period"]["start"].startswith("2025-02-01")
    assert (rep / P.HOLDOUT_FILE).exists()
    with pytest.raises(P.ProtocolError, match="TEK ATIŞ"):
        P.run_protocol("holdout", **kw)


def test_holdout_requires_insample_first(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    _write_data(data)
    with pytest.raises(P.ProtocolError, match="in-sample koşulmalı"):
        P.run_protocol("holdout", data, tmp_path / "r", ("AAA", "BBB"), PER, SP)


def test_holdout_refuses_if_insample_data_slice_changed(tmp_path):
    data, rep = tmp_path / "data", tmp_path / "reports"
    data.mkdir()
    _write_data(data)
    kw = dict(data_dir=data, report_dir=rep, symbols=("AAA", "BBB"), periods=PER, sp=SP)
    P.run_protocol("insample", **kw)
    ins = json.loads((rep / P.INSAMPLE_FILE).read_text(encoding="utf-8"))
    ins["gates_passed"] = True
    (rep / P.INSAMPLE_FILE).write_text(json.dumps(ins), encoding="utf-8")
    # in-sample dilimindeki veriyi değiştir
    other = synthetic_trend_df(n=6000, seed=99)
    save_csv(other, data / "AAA_15m.csv")
    save_csv(_htf_from(other), data / "AAA_4h.csv")
    with pytest.raises(P.ProtocolError, match="DEĞİŞMİŞ"):
        P.run_protocol("holdout", **kw)


def test_missing_data_and_start_coverage_errors(tmp_path):
    with pytest.raises(P.ProtocolError, match="veri yok"):
        P.run_protocol("insample", tmp_path, tmp_path / "r", ("NOPE",), PER, SP)
    data = tmp_path / "data"
    data.mkdir()
    _write_data(data)
    late = P.Periods(insample_start="2024-06-01", insample_end_excl="2025-02-01",
                     holdout_start="2025-02-01")
    # veri 2025-01-01'de başlıyor; dönem başı 2024-06-01 → kapsama hatası DEĞİL (veri
    # daha geç başlıyor) ama protokol bunu yakalamalı
    with pytest.raises(P.ProtocolError, match="kapsamıyor"):
        P.run_protocol("insample", data, tmp_path / "r2", ("AAA", "BBB"), late, SP)
