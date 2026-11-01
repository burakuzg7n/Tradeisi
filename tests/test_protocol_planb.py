"""Plan B v1 tek atış koşucusu: kilit, mühür, parmak izi, veri, E16, git durumu."""
import json
import shutil
import subprocess
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from tradebot import daily_data as dd
from tradebot import protocol_planb as pb
from tradebot import strategy_b as sb
from tradebot.portfolio_b import PlanBParams, PBResult, PBTrade, run_portfolio

SYMS = pb.SYMBOLS
START, END = date(2019, 10, 1), date(2025, 3, 31)
LENIENT = {"insample": {"min_pf": -1.0, "min_trades": 0, "max_dd": 100.0},
           "holdout": {"min_pf": -1.0, "max_dd": 100.0}}
STRICT = {"insample": {"min_pf": 1e9, "min_trades": 0, "max_dd": 100.0},
          "holdout": {"min_pf": -1.0, "max_dd": 100.0}}


def _make_df(seed, start=START, end=END):
    n = (end - start).days + 1
    rng = np.random.default_rng(seed)
    c = 100 * np.exp(np.cumsum(rng.normal(0.001, 0.035, n)))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) * (1 + rng.uniform(0, 0.03, n))
    l = np.minimum(o, c) * (1 - rng.uniform(0, 0.03, n))
    ts = [(dd.day_index(start) + i) * dd.DAY_MS for i in range(n)]
    return pd.DataFrame(dict(timestamp=ts, open=o, high=h, low=l, close=c, volume=1.0))


def _write_health(data, rep):
    raw, hashes, contracts = {}, {}, {}
    for s in SYMS:
        p = data / f"{s}_1d.csv"
        raw[s] = dd.load_daily_raw(p)
        hashes[s] = dd.file_sha256(p)
        contracts[s] = {"symbol": s, "contractType": "PERPETUAL", "status": "TRADING",
                        "onboardDate": int(raw[s]["timestamp"].iloc[0])}
    r = dd.build_report(raw, contracts, hashes)
    (rep / pb.HEALTH_FILE).write_text(json.dumps(r, ensure_ascii=False, default=str), encoding="utf-8")
    return r


def _env(tmp_path, mutate=None):
    data, rep = tmp_path / "data", tmp_path / "reports"
    data.mkdir()
    rep.mkdir()
    for i, s in enumerate(SYMS):
        df = _make_df(seed=10 + i)
        if mutate:
            df = mutate(s, df)
        df.to_csv(data / f"{s}_1d.csv", index=False)
    _write_health(data, rep)
    return data, rep


def run(phase, data, rep, gates=LENIENT, **kw):
    return pb.run_protocol(phase, data, rep, _allow_custom=True, _gates=gates, **kw)


# ------------------------------------------------------------------ in-sample
def test_insample_runs_sealed_and_matches_direct_engine(tmp_path):
    data, rep = _env(tmp_path)
    r = run("insample", data, rep)
    assert (rep / pb.INSAMPLE_FILE).exists() and (rep / "PLANB_INSAMPLE.lock").exists()
    assert (rep / "PLANB_INSAMPLE.md").exists()
    saved = json.loads((rep / pb.INSAMPLE_FILE).read_text(encoding="utf-8"))
    assert pb.verify_seal(saved)
    assert r["period"] == {"start": "2020-01-01", "end_inclusive": "2024-12-31"}
    # bağımsız: veri 2024-12-31'de kesilip motor doğrudan çalıştırılır
    end = dd.day_index(date(2024, 12, 31))
    frames = {}
    for s in SYMS:
        d = sb.load_daily(data / f"{s}_1d.csv")
        frames[s] = sb.compute_signals(d[d.index <= end])
    direct = run_portfolio(frames, dd.day_index(date(2020, 1, 1)), end)
    assert r["metrics"]["total_trades"] == direct.total_trades > 0
    assert float(r["metrics"]["profit_factor"]) == pytest.approx(direct.profit_factor)
    assert float(r["metrics"]["max_drawdown"]) == pytest.approx(direct.max_drawdown)
    assert all(t.exit_day <= end for t in direct.trades)
    assert pb.E13_NOTE in r["notes"]


def test_insample_single_shot(tmp_path):
    data, rep = _env(tmp_path)
    run("insample", data, rep)
    with pytest.raises(pb.ProtocolError, match="TEK ATIŞ"):
        run("insample", data, rep)


def test_insample_unaffected_by_post_period_data(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir(), b.mkdir()
    da, ra = _env(a)

    def bump(s, df):
        cut = dd.day_index(date(2025, 1, 1)) * dd.DAY_MS
        m = df["timestamp"] >= cut
        df.loc[m, ["open", "high", "low", "close"]] *= 3.0
        return df
    db, rb = _env(b, mutate=bump)
    r1, r2 = run("insample", da, ra), run("insample", db, rb)
    assert r1["metrics"] == r2["metrics"]
    assert r1["slice_hashes"] == r2["slice_hashes"]


# ------------------------------------------------------------------ hold-out kapısı
def test_holdout_requires_insample_and_pass(tmp_path):
    data, rep = _env(tmp_path)
    with pytest.raises(pb.ProtocolError, match="Önce in-sample"):
        run("holdout", data, rep)
    run("insample", data, rep, gates=STRICT)
    with pytest.raises(pb.ProtocolError, match="REDDEDİLDİ"):
        run("holdout", data, rep, gates=STRICT)
    assert not (rep / "PLANB_HOLDOUT.lock").exists()


def test_holdout_runs_after_pass_to_common_end_once(tmp_path):
    def shorter(s, df):  # SOL verisi 2025-03-20'de bitiyor → ortak bitiş
        if s == "SOLUSDT":
            df = df[df["timestamp"] <= dd.day_index(date(2025, 3, 20)) * dd.DAY_MS]
        return df
    data, rep = _env(tmp_path, mutate=shorter)
    run("insample", data, rep)
    r = run("holdout", data, rep)
    assert r["period"] == {"start": "2025-01-01", "end_inclusive": "2025-03-20"}
    assert pb.verify_seal(json.loads((rep / pb.HOLDOUT_FILE).read_text(encoding="utf-8")))
    assert "işlem >= 0" not in r["gates"]
    with pytest.raises(pb.ProtocolError, match="hold-out TEK ATIŞ"):
        run("holdout", data, rep)


def test_holdout_rejects_tampered_or_inconsistent_report(tmp_path):
    data, rep = _env(tmp_path)
    run("insample", data, rep, gates=STRICT)
    path = rep / pb.INSAMPLE_FILE
    r = json.loads(path.read_text(encoding="utf-8"))
    r["gates_passed"] = True
    path.write_text(json.dumps(r), encoding="utf-8")
    with pytest.raises(pb.ProtocolError, match="mühr"):
        run("holdout", data, rep, gates=STRICT)
    pb.seal(r)                                   # yeniden mühürlense de sayılar tutmaz
    path.write_text(json.dumps(r), encoding="utf-8")
    with pytest.raises(pb.ProtocolError, match="tutarsız"):
        run("holdout", data, rep, gates=STRICT)


def test_holdout_rejects_changed_config(tmp_path):
    data, rep = _env(tmp_path)
    run("insample", data, rep)
    with pytest.raises(pb.ProtocolError, match="farklı"):
        run("holdout", data, rep, p=PlanBParams(risk_per_trade=0.01))


def test_holdout_rejects_changed_code(tmp_path):
    root = _copy_root(tmp_path)
    data, rep = _env(tmp_path)
    run("insample", data, rep, root=root)
    with open(root / "docs" / "SPEC_EKLERI.md", "a", encoding="utf-8") as f:
        f.write("\nek kural\n")
    with pytest.raises(pb.ProtocolError, match="parmak izi"):
        run("holdout", data, rep, root=root)


def test_holdout_rejects_changed_insample_slice(tmp_path):
    data, rep = _env(tmp_path)
    run("insample", data, rep)
    p = data / "ETHUSDT_1d.csv"
    df = pd.read_csv(p)
    df.loc[500, "close"] = df.loc[500, "close"] * 1.0001
    df.to_csv(p, index=False)
    _write_health(data, rep)                     # hash'ler uyuşsun: yalnız dilim farkı kalsın
    with pytest.raises(pb.ProtocolError, match="dilimi"):
        run("holdout", data, rep)


# ------------------------------------------------------------------ veri kontrolleri (kilitten önce)
def test_data_hash_mismatch_refused_without_lock(tmp_path):
    data, rep = _env(tmp_path)
    with open(data / "BNBUSDT_1d.csv", "a") as f:
        f.write("\n")
    with pytest.raises(pb.ProtocolError, match="sha256"):
        run("insample", data, rep)
    assert not (rep / "PLANB_INSAMPLE.lock").exists()


def test_health_verdict_blocked_refused(tmp_path):
    data, rep = _env(tmp_path)
    h = json.loads((rep / pb.HEALTH_FILE).read_text(encoding="utf-8"))
    h["verdict"] = "VERİ ENGELLİ"
    (rep / pb.HEALTH_FILE).write_text(json.dumps(h), encoding="utf-8")
    with pytest.raises(pb.ProtocolError, match="Sağlık raporu"):
        run("insample", data, rep)
    assert not (rep / "PLANB_INSAMPLE.lock").exists()


def test_runtime_e14_blocker_refused(tmp_path):
    data, rep = _env(tmp_path)
    p = data / "SOLUSDT_1d.csv"
    df = pd.read_csv(p)
    df.loc[300, "high"] = df.loc[300, "low"] - 1     # bozuk bar
    df.to_csv(p, index=False)
    h = json.loads((rep / pb.HEALTH_FILE).read_text(encoding="utf-8"))
    h["symbols"]["SOLUSDT"]["file_sha256"] = dd.file_sha256(p)   # hash uyumlu, rapor "UYGUN"
    (rep / pb.HEALTH_FILE).write_text(json.dumps(h), encoding="utf-8")
    with pytest.raises(pb.ProtocolError, match="E14"):
        run("insample", data, rep)
    assert not (rep / "PLANB_INSAMPLE.lock").exists()


def test_production_guard(tmp_path):
    data, rep = _env(tmp_path)
    with pytest.raises(pb.ProtocolError, match="SABİT"):
        pb.run_protocol("insample", data, rep, _gates=LENIENT)
    with pytest.raises(pb.ProtocolError, match="SABİT"):
        pb.run_protocol("insample", data, rep, p=PlanBParams(max_positions=3))
    with pytest.raises(pb.ProtocolError, match="SABİT"):
        pb.run_protocol("insample", data, rep, symbols=("BTCUSDT",))


def test_lock_taken_before_run_and_survives_crash(tmp_path, monkeypatch):
    data, rep = _env(tmp_path)

    def boom(*a, **k):
        assert (rep / "PLANB_INSAMPLE.lock").exists()
        raise RuntimeError("çökme")
    monkeypatch.setattr(pb, "run_portfolio", boom)
    with pytest.raises(RuntimeError):
        run("insample", data, rep)
    assert (rep / "PLANB_INSAMPLE.lock").exists() and not (rep / pb.INSAMPLE_FILE).exists()
    monkeypatch.undo()
    with pytest.raises(pb.ProtocolError, match="TEK ATIŞ"):
        run("insample", data, rep)


# ------------------------------------------------------------------ git durumu
@pytest.mark.skipif(shutil.which("git") is None, reason="git yok")
def test_git_state_recorded_before_lock_and_report(tmp_path):
    root = tmp_path / "repo"
    for rel in pb._FINGERPRINT_FILES + (pb.SPEC_SECTION_FILE,):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(pb.ROOT / rel, root / rel)
    g = ["git", "-C", str(root)]
    subprocess.run(g + ["init", "-q"], check=True)
    subprocess.run(g + ["add", "-A"], check=True)
    subprocess.run(g + ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "x"], check=True)
    (root / "untracked.txt").write_text("x")
    with open(root / "tradebot" / "config.py", "a") as f:
        f.write("\n# unstaged\n")
    (root / "staged.txt").write_text("y")
    subprocess.run(g + ["add", "staged.txt"], check=True)
    data = root / "data"
    rep = root / "reports"
    data.mkdir(), rep.mkdir()
    for i, s in enumerate(SYMS):
        _make_df(seed=10 + i).to_csv(data / f"{s}_1d.csv", index=False)
    _write_health(data, rep)
    r = run("insample", data, rep, root=root)
    files = r["git"]["changed_files_before_lock"]
    joined = "\n".join(files)
    assert "untracked.txt" in joined and "staged.txt" in joined and "tradebot/config.py" in joined
    assert "PLANB_INSAMPLE.lock" not in joined and "PLANB_INSAMPLE.json" not in joined
    assert "reports/PLANB_VERI_SAGLIK.json" in joined      # kilitten önce var olan dosya
    assert r["git"]["dirty"] is True and r["git"]["commit"]


# ------------------------------------------------------------------ E16
def _trade(pnl, day):
    return PBTrade("BTCUSDT", day, day, 100, 100, 90, 1, 50, 0, 0, 0, "stop", pnl)


DAYS = list(range(100, 111))


def frame(days, overrides=None, price=100.0):
    overrides = overrides or {}
    rows = []
    for d in days:
        r = dict(open=price, high=price + 1, low=price - 1, close=price,
                 entry_signal=False, exit_signal=False, atr=5.0)
        r.update(overrides.get(d, {}))
        rows.append(r)
    return pd.DataFrame(rows, index=pd.Index(days))


def test_capital_exhausted_uses_pre_open_balance_only():
    assert pb.capital_exhausted(PBResult(counters={"days_no_capital_before_open": 1})) is True
    assert pb.capital_exhausted(PBResult(counters={"days_no_capital_before_open": 0})) is False


def test_e16_same_open_order_does_not_trigger(tmp_path):
    """ChatGPT PR #9: aynı açılışta BTC büyük zarar, ETH büyük kâr. Ara bakiye < 0 olsa da
    açılış öncesi bakiyeler hep > 0 → E16 tetiklenmez."""
    calm = {d: dict(low=100) for d in (101, 102, 103)}     # stop (99,96) tetiklenmesin
    f = {"BTCUSDT": frame(DAYS, {**calm, 100: dict(entry_signal=True, atr=0.02),
                                 104: dict(low=100, exit_signal=True),
                                 105: dict(open=50, high=51, low=49, close=50)}),
         "ETHUSDT": frame(DAYS, {**calm, 100: dict(entry_signal=True, atr=0.02),
                                 104: dict(low=100, exit_signal=True),
                                 105: dict(open=150, high=151, low=149, close=150)})}
    nocost = PlanBParams(taker_fee=0.0, slippage_rate=0.0, funding_per_day=0.0)
    r = run_portfolio(f, 100, 110, nocost)
    btc, eth = r.trades
    assert btc.pnl == pytest.approx(-50 * 1250) and eth.pnl == pytest.approx(50 * 1250)
    assert 10_000 + btc.pnl < 0                        # BTC önce işlenince ara bakiye eksi
    assert r.counters["days_no_capital_before_open"] == 0
    assert pb.capital_exhausted(r) is False
    m = pb.metrics(r, nocost, 110)
    assert m["capital_exhausted"] is False


def test_e16_triggers_when_pre_open_balance_nonpositive():
    f = {"BTCUSDT": frame(DAYS, {100: dict(entry_signal=True, atr=0.02), 101: dict(low=100),
                                 102: dict(open=80, high=81, low=79, close=80)})}
    r = run_portfolio(f, 100, 110, PlanBParams(taker_fee=0.0, slippage_rate=0.0, funding_per_day=0.0))
    assert r.trades[0].pnl == pytest.approx(-20 * 1250)
    assert r.counters["days_no_capital_before_open"] == 8     # 103..110
    assert pb.capital_exhausted(r) is True


def test_e13_liquidations_listed_with_symbol_and_date():
    sol_days = [d for d in DAYS if d != 110]                  # SOL bitiş günü (110) eksik
    f = {"BTCUSDT": frame(DAYS, {100: dict(entry_signal=True)}),
         "SOLUSDT": frame(sol_days, {100: dict(entry_signal=True), 109: dict(close=111)})}
    p = PlanBParams(taker_fee=0.0, slippage_rate=0.0, funding_per_day=0.0)
    r = run_portfolio(f, 100, 110, p)
    liq = pb.metrics(r, p, 110)["period_end_liquidations"]
    assert {x["symbol"] for x in liq["all"]} == {"BTCUSDT", "SOLUSDT"}
    (early,) = liq["early_missing_end_bar"]
    assert early["symbol"] == "SOLUSDT" and early["day"] == str(dd.day_date(109))
    assert early["price"] == pytest.approx(111.0)


def test_e16_fails_regardless_of_gates():
    m = {"profit_factor": 5.0, "total_trades": 500, "max_drawdown": 0.01, "capital_exhausted": True}
    v = pb.evaluate(m, "insample")
    assert v["passed"] is False and v["gates"]["sermaye tükenmedi (E16)"] is False
    m["capital_exhausted"] = False
    assert pb.evaluate(m, "insample")["passed"] is True
    assert pb.evaluate(m, "holdout")["passed"] is True


def test_report_lists_early_liquidations(tmp_path):
    data, rep = _env(tmp_path)
    r = run("insample", data, rep)
    liq = r["metrics"]["period_end_liquidations"]
    assert set(liq) == {"all", "early_missing_end_bar"}
    assert all(x["day"] == "2024-12-31" for x in liq["all"])   # sentetik veride bitiş barı tam
    assert liq["early_missing_end_bar"] == []
    assert "Ortak bitişten ÖNCE tasfiye" in (rep / "PLANB_INSAMPLE.md").read_text(encoding="utf-8")


def _copy_root(tmp_path):
    root = tmp_path / "root"
    for rel in pb._FINGERPRINT_FILES + (pb.SPEC_SECTION_FILE,):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(pb.ROOT / rel, root / rel)
    return root


def test_fingerprint_covers_devir_notu_section9_only(tmp_path):
    root = _copy_root(tmp_path)
    base = pb.code_fingerprint(root)
    p = root / "DEVIR_NOTU.md"
    text = p.read_text(encoding="utf-8")
    assert "## 9." in text and "## 10." in text
    p.write_text(text.replace("## 10.", "ilerleme notu eklendi\n\n## 10.", 1)
                 .replace("\n", "\r\n"), encoding="utf-8")
    # §9'un hemen sonuna (## 10'dan önce) eklenen satır §9'a dahildir → değişmeli
    assert pb.code_fingerprint(root) != base
    p.write_text(text + "\n## 99. yeni ilerleme notu\nx\n", encoding="utf-8")
    assert pb.code_fingerprint(root) == base               # §9 dışı değişiklik
    p.write_text(text.replace("\n", "\r\n"), encoding="utf-8")
    assert pb.code_fingerprint(root) == base               # yalnız satır sonu farkı
    assert text.count("son 55") == 1                      # yalnız §9'daki giriş kanalı
    p.write_text(text.replace("son 55", "son 50"), encoding="utf-8")
    assert pb.code_fingerprint(root) != base               # §9 içeriği değişti


def test_production_gates_are_e9():
    assert pb.INSAMPLE_GATES == {"min_pf": 1.3, "min_trades": 100, "max_dd": 0.15}
    assert pb.HOLDOUT_GATES == {"min_pf": 1.15, "max_dd": 0.15}
    m = {"profit_factor": 1.31, "total_trades": 100, "max_drawdown": 0.149, "capital_exhausted": False}
    assert pb.evaluate(m, "insample")["passed"] is True
    for k, v in (("profit_factor", 1.3), ("total_trades", 99), ("max_drawdown", 0.15)):
        assert pb.evaluate({**m, k: v}, "insample")["passed"] is False


def test_holdout_ignores_thresholds_stored_in_report(tmp_path):
    """Rapordaki eşikler gevşetilip yeniden mühürlense de kapılar KODDAKİ eşiklerle hesaplanır."""
    data, rep = _env(tmp_path)
    run("insample", data, rep, gates=STRICT)
    path = rep / pb.INSAMPLE_FILE
    r = json.loads(path.read_text(encoding="utf-8"))
    r["gate_thresholds"] = LENIENT["insample"]
    r["gates_passed"] = True
    r["verdict"] = "GEÇTİ"
    pb.seal(r)
    path.write_text(json.dumps(r), encoding="utf-8")
    with pytest.raises(pb.ProtocolError, match="tutarsız"):
        run("holdout", data, rep, gates=STRICT)
    assert not (rep / "PLANB_HOLDOUT.lock").exists()
