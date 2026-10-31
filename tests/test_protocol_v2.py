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
    start, end = ltf.index[2000], ltf.index[4800]
    res, info = P.run_period(ltf, htf, start.isoformat(), end, SP, BacktestParams())
    assert info["period_first_bar"] == str(start)
    # dönem sonrası veri kullanılmaz: son bar end'den önce
    assert pd.Timestamp(info["period_last_bar"]) < end
    # kesilmiş veri + dönem başı = aynı emir kümesi (kesme ve E3c durum sıfırlama uygulandı)
    ltf_c, htf_c = ltf[ltf.index < end], htf[htf.index < end]
    want = generate_orders_v2(ltf_c, htf_c, SP, trade_from_idx=2000)
    assert info["orders_generated"] == len(want) == info["orders_in_period"]
    assert all(o.created_idx >= 2000 for o in want)
    # ısınma gerçekten kullanılıyor: dönem başında sıfırdan başlayan veriyle FARKLI olabilir
    cold = generate_orders_v2(ltf_c.iloc[2000:], htf_c, SP)
    assert isinstance(cold, list)


def test_period_start_resets_setup_state_no_carryover():
    """E3c: dönem öncesi barlar yalnız gösterge ısınması. Sweep'i dönem ÖNCESİNDE olan
    setup'tan doğan emir dönem içinde alınmamalı."""
    ltf = synthetic_trend_df(n=6000, seed=7)
    htf = _htf_from(ltf)
    full = generate_orders_v2(ltf, htf, SP)
    carried = [o for o in full if o.meta["sweep_idx"] < o.created_idx - 1]
    assert carried, "sweep'i emirden önce olan emir bulunmalı; test anlamsız kalmasın"
    o = carried[0]
    start = o.meta["sweep_idx"] + 1
    part = generate_orders_v2(ltf, htf, SP, trade_from_idx=start)
    assert all(x.meta["sweep_idx"] >= start for x in part), "dönem öncesi setup taşındı"
    assert _sig(generate_orders_v2(ltf, htf, SP, trade_from_idx=0)) == _sig(full)
    assert len(part) > 0                                # ısınma sonrası yine emir üretir
    # run_period üzerinden de: işlemlerin sweep'i dönem içinde
    res, info = P.run_period(ltf, htf, ltf.index[start].isoformat(), ltf.index[5000], SP,
                             BacktestParams())
    assert all(t.meta["sweep_idx"] >= start for t in res.trades)


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


def test_liquidate_at_end_short_costs_are_exact():
    bars = [(100, 101, 99, 100), (100, 101, 99, 100), (100, 101, 99, 99.5)]
    o = _order(side="short", entry=100.0, stop=105.0, target=80.0)
    bt = _bt_costly()
    r = bt.run(make_df(bars), [o], liquidate_at_end=True)
    assert len(r.trades) == 1 and r.forced_closes == 1
    fill = 100 * 0.999
    size = 10_000 * bt.p.risk_per_trade / (105 - fill)
    exit_px = 99.5 * 1.001
    pnl = (fill - exit_px) * size - fill * size * 0.001 - exit_px * size * 0.001
    assert r.trades[0].exit_reason == "period_end"
    assert r.trades[0].pnl_usd == pytest.approx(pnl)


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
    a = _result([10], [10_000, 9_000, 10_000, 10_000])
    b = _result([0], [10_000, 10_000])
    b.equity_curve.index = a.equity_curve.index[2:]     # B ikinci yarıda başlar
    c = P.combine({"A": a, "B": b}, 10_000)
    assert c["final_total"] == pytest.approx(20_000)
    # erken dönem: toplam = A + 10.000 (B başlangıç bakiyesiyle doldurulur)
    # → [20000, 19000, 20000, 20000], DD = 1000/20000 = %5. Yanlış dolgu (0) %10 verirdi.
    assert c["max_drawdown"] == pytest.approx(0.05)


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
def _env(tmp_path, n=6000):
    data, rep = tmp_path / "data", tmp_path / "reports"
    data.mkdir()
    _write_data(data, n=n)
    return data, rep, dict(data_dir=data, report_dir=rep, symbols=("AAA", "BBB"),
                           periods=PER, sp=SP, _allow_custom=True)


def _force(rep, **comb):
    """Raporu (testte) 'geçti' ya da 'kaldı' gibi yeniden mühürle."""
    ins = json.loads((rep / P.INSAMPLE_FILE).read_text(encoding="utf-8"))
    ins["combined"].update(comb)
    ok = P._recompute_pass(ins)
    ins["gates_passed"], ins["verdict"] = ok, ("GEÇTİ" if ok else "KALDI")
    (rep / P.INSAMPLE_FILE).write_text(json.dumps(P.seal(ins)), encoding="utf-8")
    return ins


PASS = dict(profit_factor=2.0, total_trades=200, max_drawdown=0.05)
FAIL = dict(profit_factor=0.8, total_trades=200, max_drawdown=0.05)


def test_single_shot_lock_and_holdout_gating(tmp_path):
    data, rep, kw = _env(tmp_path)
    r = P.run_protocol("insample", **kw)
    assert (rep / P.INSAMPLE_FILE).exists() and (rep / "V2_INSAMPLE.md").exists()
    assert (rep / "V2_INSAMPLE.lock").exists()
    assert r["period"]["end_exclusive"].startswith("2025-02-01")
    assert P.verify_seal(json.loads((rep / P.INSAMPLE_FILE).read_text(encoding="utf-8")))
    with pytest.raises(P.ProtocolError, match="TEK ATIŞ"):
        P.run_protocol("insample", **kw)

    _force(rep, **FAIL)                                     # KALDI → hold-out reddedilir
    with pytest.raises(P.ProtocolError, match="REDDEDİLDİ"):
        P.run_protocol("holdout", **kw)

    ins = _force(rep, **PASS)
    ins["code_fingerprint"] = "0" * 64                      # kod değişmiş
    (rep / P.INSAMPLE_FILE).write_text(json.dumps(P.seal(ins)), encoding="utf-8")
    with pytest.raises(P.ProtocolError, match="parmak izi"):
        P.run_protocol("holdout", **kw)

    ins = _force(rep, **PASS)
    ins["code_fingerprint"] = P.code_fingerprint()
    (rep / P.INSAMPLE_FILE).write_text(json.dumps(P.seal(ins)), encoding="utf-8")
    ho = P.run_protocol("holdout", **kw)                    # her şey tutarlı: koşar
    assert ho["phase"] == "holdout" and ho["period"]["start"].startswith("2025-02-01")
    assert P.verify_seal(ho)
    with pytest.raises(P.ProtocolError, match="TEK ATIŞ"):
        P.run_protocol("holdout", **kw)


def _sealed_pass(rep):
    ins = _force(rep, **PASS)
    ins["code_fingerprint"] = P.code_fingerprint()
    (rep / P.INSAMPLE_FILE).write_text(json.dumps(P.seal(ins)), encoding="utf-8")


def test_holdout_requires_insample_first(tmp_path):
    data, rep, kw = _env(tmp_path)
    with pytest.raises(P.ProtocolError, match="in-sample koşulmalı"):
        P.run_protocol("holdout", **kw)


def test_holdout_rejects_edited_report_without_reseal(tmp_path):
    """gates_passed elle true yapılırsa (mühür bozulur) hold-out açılmaz."""
    data, rep, kw = _env(tmp_path)
    P.run_protocol("insample", **kw)
    ins = json.loads((rep / P.INSAMPLE_FILE).read_text(encoding="utf-8"))
    ins["gates_passed"] = True
    (rep / P.INSAMPLE_FILE).write_text(json.dumps(ins), encoding="utf-8")
    with pytest.raises(P.ProtocolError, match="bütünlük"):
        P.run_protocol("holdout", **kw)


def test_holdout_rejects_inconsistent_gates_even_if_resealed(tmp_path):
    """Mühürlenmiş olsa bile kapılar yeniden hesaplanır: PF 0.8 iken 'true' kabul edilmez."""
    data, rep, kw = _env(tmp_path)
    P.run_protocol("insample", **kw)
    ins = _force(rep, **FAIL)
    ins["gates_passed"] = True                              # sahte
    ins["code_fingerprint"] = P.code_fingerprint()
    (rep / P.INSAMPLE_FILE).write_text(json.dumps(P.seal(ins)), encoding="utf-8")
    with pytest.raises(P.ProtocolError, match="tutarsız"):
        P.run_protocol("holdout", **kw)


def test_holdout_rejects_changed_params_or_symbols(tmp_path):
    data, rep, kw = _env(tmp_path)
    P.run_protocol("insample", **kw)
    _sealed_pass(rep)
    with pytest.raises(P.ProtocolError, match="parametreleri"):
        P.run_protocol("holdout", **{**kw, "sp": replace(SP, use_session_filter=True)})
    with pytest.raises(P.ProtocolError, match="parametreleri"):
        P.run_protocol("holdout", **{**kw, "bp": BacktestParams(taker_fee=0.0001)})
    with pytest.raises(P.ProtocolError, match="parametreleri"):
        P.run_protocol("holdout", **{**kw, "symbols": ("AAA",)})       # ETH'siz değerlendirme
    with pytest.raises(P.ProtocolError, match="parametreleri"):
        P.run_protocol("holdout", **{**kw, "periods": P.Periods(
            insample_start="2025-01-01", insample_end_excl="2025-02-01",
            holdout_start="2025-02-05")})


def test_holdout_refuses_if_insample_data_slice_changed(tmp_path):
    data, rep, kw = _env(tmp_path)
    P.run_protocol("insample", **kw)
    _sealed_pass(rep)
    other = synthetic_trend_df(n=6000, seed=99)
    save_csv(other, data / "AAA_15m.csv")
    save_csv(_htf_from(other), data / "AAA_4h.csv")
    with pytest.raises(P.ProtocolError, match="DEĞİŞMİŞ"):
        P.run_protocol("holdout", **kw)


def test_production_protocol_rejects_custom_parameters(tmp_path):
    data, rep, kw = _env(tmp_path)
    kw.pop("_allow_custom")
    with pytest.raises(P.ProtocolError, match="SABİT"):
        P.run_protocol("insample", **kw)
    assert not (rep / "V2_INSAMPLE.lock").exists()          # reddedilen koşu kilit tüketmez


def test_lock_taken_before_run_and_survives_crash(tmp_path, monkeypatch):
    data, rep, kw = _env(tmp_path)
    def boom(*a, **k):
        raise RuntimeError("koşu ortasında çöktü")
    monkeypatch.setattr(P, "run_period", boom)
    with pytest.raises(RuntimeError):
        P.run_protocol("insample", **kw)
    assert (rep / "V2_INSAMPLE.lock").exists() and not (rep / P.INSAMPLE_FILE).exists()
    monkeypatch.undo()
    with pytest.raises(P.ProtocolError, match="TEK ATIŞ"):   # çöken koşu da hakkı tüketti
        P.run_protocol("insample", **kw)


def test_preexisting_lock_blocks_run(tmp_path):
    data, rep, kw = _env(tmp_path)
    rep.mkdir()
    (rep / "V2_INSAMPLE.lock").write_text("başka süreç", encoding="utf-8")
    with pytest.raises(P.ProtocolError, match="TEK ATIŞ"):
        P.run_protocol("insample", **kw)


def test_coverage_errors_do_not_consume_the_shot(tmp_path):
    with pytest.raises(P.ProtocolError, match="veri yok"):
        P.run_protocol("insample", tmp_path, tmp_path / "r", ("NOPE",), PER, SP,
                       _allow_custom=True)
    # veri dönem sonuna ulaşmıyor (n=1000 → ~10 gün; dönem sonu 2025-02-01)
    data, rep, kw = _env(tmp_path / "short", n=1000) if (tmp_path / "short").mkdir() is None else None
    with pytest.raises(P.ProtocolError, match="ulaşmıyor"):
        P.run_protocol("insample", **kw)
    assert not (rep / "V2_INSAMPLE.lock").exists()
    # dönem başı veriden önce
    data2 = tmp_path / "d2"
    data2.mkdir()
    _write_data(data2)
    early = P.Periods(insample_start="2024-06-01", insample_end_excl="2025-02-01",
                      holdout_start="2025-02-01")
    with pytest.raises(P.ProtocolError, match="kapsamıyor"):
        P.run_protocol("insample", data2, tmp_path / "r2", ("AAA", "BBB"), early, SP,
                       _allow_custom=True)


def _htf_variant(data, symbol, keep):
    """4h dosyasını `keep(htf)` ile değiştir (15m dokunulmaz)."""
    from tradebot.data import load_csv
    h = load_csv(data / f"{symbol}_4h.csv")
    save_csv(keep(h), data / f"{symbol}_4h.csv")


def test_htf_coverage_gaps_are_rejected_without_consuming_the_shot(tmp_path):
    for label, keep, msg in (
        ("yalniz son iki bar", lambda h: h.iloc[-2:], "kapsamıyor"),
        ("ilk yarisi eksik", lambda h: h.iloc[len(h) // 2:], "kapsamıyor"),
        ("ortadan buyuk kayip", lambda h: h.drop(h.index[100:160]), "kapsama oranı"),
    ):
        base = tmp_path / label.replace(" ", "_")
        base.mkdir()
        data, rep, kw = _env(base)
        _htf_variant(data, "AAA", keep)
        with pytest.raises(P.ProtocolError, match=msg):
            P.run_protocol("insample", **kw)
        assert not (rep / "V2_INSAMPLE.lock").exists(), label
