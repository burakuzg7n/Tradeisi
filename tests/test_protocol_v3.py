"""V3 tek atış koşucusu: kilit, mühür, parmak izi, veri kontrolleri, kapılar (sentetik veri)."""
import json
import math
import shutil
import subprocess
from datetime import date

import numpy as np
import pandas as pd
import pytest

from tradebot import daily_data as dd
from tradebot import protocol_v3 as pv
from tradebot import strategy_v3 as sv
from tradebot import v3_data as vd
from tradebot.engine_v3 import V3Params, run_v3
from tradebot.synthetic_v3 import generate

SYMS = pv.SYMBOLS
PER = pv.Periods(insample_start="2021-01-01", insample_end="2021-02-28", holdout_start="2021-03-01")
D0, D1 = date(2020, 11, 1), date(2021, 3, 31)
LENIENT = {"insample": {"min_pf": -1.0, "min_trades": 0, "min_mean": -1e9, "min_t": -1e9, "max_dd": 100.0},
           "holdout": {"min_pf": -1.0, "min_mean": -1e9, "max_dd": 100.0}}
STRICT = {"insample": {"min_pf": 1e9, "min_trades": 0, "min_mean": -1e9, "min_t": -1e9, "max_dd": 100.0},
          "holdout": {"min_pf": -1.0, "min_mean": -1e9, "max_dd": 100.0}}


def _write_health(data, rep_dir):
    raw, hashes, contracts = {}, {}, {}
    for s in SYMS:
        p = data / f"{s}_15m.csv"
        raw[s] = dd.load_daily_raw(p)
        hashes[s] = dd.file_sha256(p)
        contracts[s] = {"contractType": "PERPETUAL", "status": "TRADING",
                        "onboardDate": int(raw[s]["timestamp"].iloc[0])}
    r = vd.build_report(raw, contracts, hashes, insample=(date(2021, 1, 1), date(2021, 2, 28)),
                        holdout_start=date(2021, 3, 1))
    (rep_dir / pv.HEALTH_FILE).write_text(json.dumps(r, ensure_ascii=False, default=str), encoding="utf-8")
    return r


def _env(tmp_path, mutate=None, seed=5):
    data, rep = tmp_path / "data", tmp_path / "reports"
    data.mkdir(parents=True)
    rep.mkdir(parents=True)
    n = (D1 - D0).days + 1
    frames = generate(SYMS, vd.day_index(D0), n, 0.04, 0.6, "trend", seed)
    for s in SYMS:
        df = frames[s].copy()
        out = pd.DataFrame(dict(timestamp=df.index.astype("int64"), open=df["open"], high=df["high"],
                                low=df["low"], close=df["close"], volume=1.0)).reset_index(drop=True)
        if mutate:
            out = mutate(s, out)
        out.to_csv(data / f"{s}_15m.csv", index=False)
    _write_health(data, rep)
    return data, rep


def run(phase, data, rep, gates=LENIENT, **kw):
    kw.setdefault("periods", PER)
    return pv.run_protocol(phase, data, rep, _allow_custom=True, _gates=gates, **kw)


def _copy_root(tmp_path):
    root = tmp_path / "root"
    for rel in pv._FINGERPRINT_FILES:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(pv.ROOT / rel, root / rel)
    return root


# ------------------------------------------------------------------ in-sample
def test_insample_sealed_and_matches_direct_engine(tmp_path):
    data, rep = _env(tmp_path)
    r = run("insample", data, rep)
    assert pv.verify_seal(json.loads((rep / pv.INSAMPLE_FILE).read_text(encoding="utf-8")))
    assert (rep / "V3_INSAMPLE.lock").exists() and (rep / "V3_INSAMPLE.md").exists()
    assert r["period"] == {"start": "2021-01-01", "end_inclusive": "2021-02-28"}
    s, e = vd.day_index(date(2021, 1, 1)), vd.day_index(date(2021, 2, 28))
    bars = {x: vd.load_15m(data / f"{x}_15m.csv") for x in SYMS}
    bars = {x: b[b.index < (e + 1) * vd.DAY_MS] for x, b in bars.items()}
    intents = {x: sv.generate_intents(x, bars[x], s, e) for x in SYMS}
    direct = run_v3(bars, intents, s, e, V3Params())
    assert r["metrics"]["total_trades"] == len(direct.trades) > 20
    assert float(r["metrics"]["profit_factor"]) == pytest.approx(direct.profit_factor)
    assert float(r["metrics"]["max_drawdown"]) == pytest.approx(direct.max_drawdown)
    assert r["notes"] == pv.NOTES


def test_insample_single_shot(tmp_path):
    data, rep = _env(tmp_path)
    run("insample", data, rep)
    with pytest.raises(pv.ProtocolError, match="TEK ATIŞ"):
        run("insample", data, rep)


def test_insample_unaffected_by_post_period_data(tmp_path):
    def bump(s, df):
        m = df["timestamp"] >= vd.day_index(date(2021, 3, 1)) * vd.DAY_MS
        df.loc[m, ["open", "high", "low", "close"]] *= 2.0
        return df
    da, ra = _env(tmp_path / "a")
    db, rb = _env(tmp_path / "b", mutate=bump)
    r1, r2 = run("insample", da, ra), run("insample", db, rb)
    assert r1["metrics"] == r2["metrics"] and r1["slice_hashes"] == r2["slice_hashes"]


# ------------------------------------------------------------------ hold-out
def test_holdout_gating_and_single_shot(tmp_path):
    data, rep = _env(tmp_path)
    with pytest.raises(pv.ProtocolError, match="Önce in-sample"):
        run("holdout", data, rep)
    run("insample", data, rep, gates=STRICT)
    with pytest.raises(pv.ProtocolError, match="REDDEDİLDİ"):
        run("holdout", data, rep, gates=STRICT)
    assert not (rep / "V3_HOLDOUT.lock").exists()


def test_holdout_runs_to_d_son(tmp_path):
    data, rep = _env(tmp_path)
    run("insample", data, rep)
    r = run("holdout", data, rep)
    assert r["period"] == {"start": "2021-03-01", "end_inclusive": "2021-03-31"}
    assert "işlem >= 0" not in r["gates"] and not any("HAC" in k for k in r["gates"])
    with pytest.raises(pv.ProtocolError, match="hold-out TEK ATIŞ"):
        run("holdout", data, rep)


def test_holdout_rejects_tamper_inconsistency_and_stored_thresholds(tmp_path):
    data, rep = _env(tmp_path)
    run("insample", data, rep, gates=STRICT)
    path = rep / pv.INSAMPLE_FILE
    r = json.loads(path.read_text(encoding="utf-8"))
    r["gates_passed"] = True
    path.write_text(json.dumps(r), encoding="utf-8")
    with pytest.raises(pv.ProtocolError, match="mühr"):
        run("holdout", data, rep, gates=STRICT)
    r["gate_thresholds"] = LENIENT["insample"]
    pv.seal(r)
    path.write_text(json.dumps(r), encoding="utf-8")
    with pytest.raises(pv.ProtocolError, match="tutarsız"):
        run("holdout", data, rep, gates=STRICT)


def test_holdout_rejects_config_code_and_slice_changes(tmp_path):
    data, rep = _env(tmp_path)
    root = _copy_root(tmp_path)
    run("insample", data, rep, root=root)
    with pytest.raises(pv.ProtocolError, match="farklı"):
        run("holdout", data, rep, root=root, p=V3Params(slippage=0.0005))
    with open(root / "docs" / "V3_SPEC_TASLAK.md", "a", encoding="utf-8") as f:
        f.write("\nek\n")
    with pytest.raises(pv.ProtocolError, match="parmak izi"):
        run("holdout", data, rep, root=root)


def test_holdout_rejects_changed_insample_slice(tmp_path):
    data, rep = _env(tmp_path)
    run("insample", data, rep)
    p = data / "ADAUSDT_15m.csv"
    df = pd.read_csv(p)
    k = int(np.flatnonzero(df["timestamp"].to_numpy() == vd.day_index(date(2021, 1, 20)) * vd.DAY_MS)[0])
    df.loc[k, "close"] = min(df.loc[k, "high"], df.loc[k, "close"] * 1.0001)
    df.loc[k, "high"] = max(df.loc[k, "high"], df.loc[k, "close"])
    df.to_csv(p, index=False)
    _write_health(data, rep)
    with pytest.raises(pv.ProtocolError, match="dilimi"):
        run("holdout", data, rep)


# ------------------------------------------------------------------ veri (kilitten önce)
def test_hash_mismatch_refused_without_lock(tmp_path):
    data, rep = _env(tmp_path)
    with open(data / "LINKUSDT_15m.csv", "a") as f:
        f.write("\n")
    with pytest.raises(pv.ProtocolError, match="sha256"):
        run("insample", data, rep)
    assert not (rep / "V3_INSAMPLE.lock").exists()


def test_health_blocked_refused(tmp_path):
    data, rep = _env(tmp_path)
    h = json.loads((rep / pv.HEALTH_FILE).read_text(encoding="utf-8"))
    h["verdict"] = "VERİ ENGELLİ"
    (rep / pv.HEALTH_FILE).write_text(json.dumps(h), encoding="utf-8")
    with pytest.raises(pv.ProtocolError, match="Sağlık"):
        run("insample", data, rep)
    assert not (rep / "V3_INSAMPLE.lock").exists()


def test_runtime_blocker_refused(tmp_path):
    def bad(s, df):
        if s == "XRPUSDT":
            df.loc[3000, "high"] = df.loc[3000, "low"] - 0.01
        return df
    data, rep = _env(tmp_path, mutate=bad)
    h = json.loads((rep / pv.HEALTH_FILE).read_text(encoding="utf-8"))
    h["verdict"], h["blockers"] = "VERİ UYGUN", []
    (rep / pv.HEALTH_FILE).write_text(json.dumps(h), encoding="utf-8")
    with pytest.raises(pv.ProtocolError, match="engeli"):
        run("insample", data, rep)
    assert not (rep / "V3_INSAMPLE.lock").exists()


def test_misaligned_bar_rejected_before_lock(tmp_path):
    def mis(s, df):
        if s == "DOGEUSDT":
            df.loc[5, "timestamp"] += 60_000
        return df
    data, rep = _env(tmp_path, mutate=mis)
    h = json.loads((rep / pv.HEALTH_FILE).read_text(encoding="utf-8"))
    assert h["verdict"] == "VERİ ENGELLİ" or any("hizalı" in w for w in h["symbols"]["DOGEUSDT"]["warnings"])
    h["verdict"], h["blockers"] = "VERİ UYGUN", []
    (rep / pv.HEALTH_FILE).write_text(json.dumps(h), encoding="utf-8")
    with pytest.raises(pv.ProtocolError):
        run("insample", data, rep)
    assert not (rep / "V3_INSAMPLE.lock").exists()


def test_production_guard(tmp_path):
    data, rep = _env(tmp_path)
    for kw in (dict(_gates=LENIENT), dict(periods=PER), dict(p=V3Params(risk_per_trade=0.005)),
               dict(symbols=("XRPUSDT",))):
        with pytest.raises(pv.ProtocolError, match="SABİT"):
            pv.run_protocol("insample", data, rep, **kw)


def test_lock_before_run_survives_crash(tmp_path, monkeypatch):
    data, rep = _env(tmp_path)

    def boom(*a, **k):
        assert (rep / "V3_INSAMPLE.lock").exists()
        raise RuntimeError("çökme")
    monkeypatch.setattr(pv, "run_v3", boom)
    with pytest.raises(RuntimeError):
        run("insample", data, rep)
    assert (rep / "V3_INSAMPLE.lock").exists() and not (rep / pv.INSAMPLE_FILE).exists()


@pytest.mark.skipif(shutil.which("git") is None, reason="git yok")
def test_git_state_before_lock(tmp_path):
    root = _copy_root(tmp_path)
    g = ["git", "-C", str(root)]
    subprocess.run(g + ["init", "-q"], check=True)
    subprocess.run(g + ["add", "-A"], check=True)
    subprocess.run(g + ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "x"], check=True)
    data, rep = _env(root)
    r = run("insample", data, rep, root=root)
    joined = "\n".join(r["git"]["changed_files_before_lock"])
    assert "V3_VERI_SAGLIK.json" in joined and "V3_INSAMPLE.lock" not in joined


# ------------------------------------------------------------------ kapılar
def _m(**kw):
    base = {"profit_factor": 1.31, "total_trades": 1300, "max_drawdown": 0.299,
            "capital_exhausted": False, "daily": {"mean": 0.001, "hac_t": 2.01}}
    base.update(kw)
    return base


def test_production_gates_and_edges():
    assert pv.INSAMPLE_GATES == {"min_pf": 1.3, "min_trades": 1300, "min_mean": 0.0, "min_t": 2.0,
                                 "max_dd": 0.30}
    assert pv.HOLDOUT_GATES == {"min_pf": 1.15, "min_mean": 0.0, "max_dd": 0.30}
    assert pv.evaluate(_m(), "insample")["passed"] is True
    for kw in (dict(profit_factor=1.3), dict(total_trades=1299), dict(max_drawdown=0.30),
               dict(capital_exhausted=True), dict(daily={"mean": 0.0, "hac_t": 5.0}),
               dict(daily={"mean": 0.001, "hac_t": 2.0}),
               dict(daily={"mean": 0.001, "hac_t": float("nan")})):
        assert pv.evaluate(_m(**kw), "insample")["passed"] is False, kw
    assert pv.evaluate(_m(profit_factor=1.16, total_trades=5, daily={"mean": 0.001, "hac_t": float("nan")}),
                       "holdout")["passed"] is True
    assert pv.evaluate(_m(profit_factor=1.16, daily={"mean": -0.001, "hac_t": 3}), "holdout")["passed"] is False


def test_raw_archive_allows_independent_recompute(tmp_path):
    data, rep = _env(tmp_path)
    r = run("insample", data, rep)
    a = r["archive"]
    for k in ("trades", "daily", "equity"):
        assert pv.dd.file_sha256(rep / a[k]["file"]) == a[k]["sha256"]
    tr = pd.read_csv(rep / a["trades"]["file"])
    assert len(tr) == r["metrics"]["total_trades"]
    gp, gl = tr.loc[tr.pnl > 0, "pnl"].sum(), -tr.loc[tr.pnl <= 0, "pnl"].sum()
    assert gp / gl == pytest.approx(float(r["metrics"]["profit_factor"]))
    eq = pd.read_csv(rep / a["equity"]["file"])["equity"].to_numpy()
    peak = np.maximum.accumulate(eq)
    assert ((peak - eq) / peak).max() == pytest.approx(float(r["metrics"]["max_drawdown"]))
    daily = pd.read_csv(rep / a["daily"]["file"])
    m, se, L, t = pv.newey_west_t(daily["r_d"].to_numpy())
    assert t == pytest.approx(float(r["metrics"]["daily"]["hac_t"]))
    assert daily["r_d"].sum() * 10_000 == pytest.approx(tr["pnl"].sum())


def test_archive_trades_csv_has_header_without_trades(tmp_path):
    from tradebot.engine_v3 import V3Result
    res = V3Result(trades=[], equity=pd.Series([10_000.0], index=[0]), start_day=1, end_day=2)
    a = pv._write_archive(res, V3Params(), tmp_path / "V3_INSAMPLE.json")
    tr = pd.read_csv(tmp_path / a["trades"]["file"])
    assert len(tr) == 0 and "pnl" in tr.columns and "r" in tr.columns
