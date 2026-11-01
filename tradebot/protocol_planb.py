"""Plan B v1 test protokolü (DEVIR_NOTU §9 + docs/SPEC_EKLERI.md E3b, E3c, E5–E9, E11–E17).

TEK ATIŞ KURALLARI (kod ile zorlanır):
- insample: yalnız BİR kez koşar (reports/PLANB_INSAMPLE.json veya .lock varsa reddeder).
  Yeniden koşmak = yeni versiyon (Plan B.1) + yeni tek atış; dosyalar elle silinmez.
- holdout: yalnız in-sample GEÇTİYSE, mühür ve kapılar doğrulanırsa, kod parmak izi,
  protokol yapılandırması ve in-sample veri dilimi DEĞİŞMEDİYSE ve daha önce
  koşmadıysa çalışır.
- Kilit, TÜM doğrulamalar geçtikten sonra ve koşudan ÖNCE atomik olarak alınır.
- Git durumu (staged, unstaged, untracked) kilit ve rapor oluşmadan ÖNCE kaydedilir.
- Parametreler sabittir (portfolio_b.PlanBParams, strategy_b sabitleri); optimize edilmez.

Veri: data/{SEMBOL}_1d.csv. Dosyaların sha256'sı reports/PLANB_VERI_SAGLIK.json'daki
değerlerle AYNI olmalı; E14 engelleri koşu anında yeniden hesaplanır.

Dönemler: in-sample 2020-01-01 → 2024-12-31 (dahil); hold-out 2025-01-01 → ortak bitiş
(sembollerin son tam gününün en erkeni, E13). Sinyaller dönem sonundan SONRAKİ veri
kesilerek hesaplanır. Dönem öncesi veri yalnız ısınma içindir (E3c).

Kapılar (E9): in-sample PF > 1,3 VE DD < %15 VE işlem ≥ 100; hold-out PF > 1,15 VE
DD < %15. E16: dönem içinde gerçekleşmiş bakiye ≤ 0 olduysa kapılardan bağımsız KALDI.

Bilinen istisna (E13): dönem sonu tasfiyesi, sembolün dönem içindeki son mevcut barını
dönem sonu verisine bakarak belirler. Bu, onaylanmış bir dönem sonu varsayımıdır; rapor
bu nedenle genel bir "lookahead yok" iddiası taşımaz. Sinyal hesabında lookahead yoktur
(tests/test_strategy_b.py).

Güvenlik notu: kilitler yerel dosyalara dayanır. Dosya silmek, başka report_dir
kullanmak veya kodu değiştirmek bilinçli müdahaledir ve kodla ENGELLENEMEZ. Gerçek
güvence: sonuç raporunun HEMEN git'e commit edilmesi ve bağımsız denetim (AGENTS.md).
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import daily_data as dd
from . import strategy_b as sb
from .portfolio_b import PRIORITY, PlanBParams, PBResult, run_portfolio
from .protocol_v2 import _acquire_lock, _clean, _norm_bytes, seal, verify_seal

ROOT = Path(__file__).resolve().parents[1]
VERSION = "PLANB_V1"
SYMBOLS = PRIORITY
INSAMPLE_FILE = "PLANB_INSAMPLE.json"
HOLDOUT_FILE = "PLANB_HOLDOUT.json"
HEALTH_FILE = "PLANB_VERI_SAGLIK.json"

# E9 — DEĞİŞTİRİLEMEZ
INSAMPLE_GATES = {"min_pf": 1.3, "min_trades": 100, "max_dd": 0.15}
HOLDOUT_GATES = {"min_pf": 1.15, "max_dd": 0.15}

_FINGERPRINT_FILES = (
    "tradebot/portfolio_b.py", "tradebot/strategy_b.py", "tradebot/daily_data.py",
    "tradebot/config.py", "tradebot/protocol_planb.py", "tradebot/protocol_v2.py",
    "docs/SPEC_EKLERI.md",
)

E13_NOTE = ("E13: dönem sonu tasfiyesi sembolün dönem içindeki son mevcut barını dönem "
            "sonu verisine bakarak belirler (onaylanmış dönem sonu varsayımı). Bu rapor genel "
            "bir 'lookahead yok' iddiası taşımaz; sinyal hesabı lookahead içermez.")


class ProtocolError(RuntimeError):
    """Protokol kuralı ihlali: koşu reddedilir."""


@dataclasses.dataclass(frozen=True)
class Periods:
    insample_start: str = str(dd.INSAMPLE_START)   # 2020-01-01
    insample_end: str = str(dd.INSAMPLE_END)       # 2024-12-31 (dahil)
    holdout_start: str = str(dd.HOLDOUT_START)     # 2025-01-01


def _day(s: str) -> int:
    return dd.day_index(datetime.strptime(s, "%Y-%m-%d").date())


# ----------------------------------------------------------------- parmak izi / git
def code_fingerprint(root: Path = ROOT) -> str:
    h = hashlib.sha256()
    for rel in _FINGERPRINT_FILES:
        f = root / rel
        h.update(rel.encode())
        h.update(_norm_bytes(f))
    return h.hexdigest()


def git_state(root: Path = ROOT) -> dict:
    """Kilit/rapor oluşmadan ÖNCE çağrılır. staged + unstaged + untracked dosyalar."""
    def run(*a):
        p = subprocess.run(["git", *a], cwd=root, capture_output=True, text=True, timeout=20)
        if p.returncode != 0:
            raise RuntimeError(p.stderr.strip())
        return p.stdout
    try:
        commit = run("rev-parse", "HEAD").strip() or None
        lines = [l for l in run("status", "--porcelain=v1", "--untracked-files=all").splitlines() if l]
        return {"commit": commit, "changed_files_before_lock": lines, "dirty": bool(lines)}
    except Exception as e:  # git yoksa veya depo değilse
        return {"commit": None, "changed_files_before_lock": None, "dirty": None,
                "error": str(e)[:200]}


# ----------------------------------------------------------------- veri
def _frame_rows_hash(df: pd.DataFrame) -> str:
    h = hashlib.sha256()
    h.update(np.ascontiguousarray(df.index.to_numpy(dtype="int64")).tobytes())
    h.update(np.ascontiguousarray(df[["open", "high", "low", "close"]].to_numpy(dtype="float64")).tobytes())
    return h.hexdigest()


def load_and_check_data(data_dir: Path, report_dir: Path, symbols) -> tuple[dict, dict, dict]:
    """CSV'leri yükler; sağlık raporu hash'leri ve E14 engelleri kontrol edilir."""
    hp = report_dir / HEALTH_FILE
    if not hp.exists():
        raise ProtocolError(f"{HEALTH_FILE} yok: önce veri indirilip sağlık raporu üretilmeli.")
    health = json.loads(hp.read_text(encoding="utf-8"))
    if health.get("verdict") != "VERİ UYGUN":
        raise ProtocolError(f"Sağlık raporu: {health.get('verdict')}. Koşu yapılmaz (E14).")
    raw, daily, hashes = {}, {}, {}
    for s in symbols:
        p = data_dir / f"{s}_1d.csv"
        if not p.exists():
            raise ProtocolError(f"[{s}] veri yok: {p.name}")
        hashes[s] = dd.file_sha256(p)
        want = (health.get("symbols", {}).get(s) or {}).get("file_sha256")
        if hashes[s] != want:
            raise ProtocolError(f"[{s}] {p.name} sha256 sağlık raporundakiyle AYNI DEĞİL "
                                "(dosya değişmiş/yeniden indirilmiş).")
        raw[s] = dd.load_daily_raw(p)
        daily[s] = sb.load_daily(p)
    contracts = {s: (health["symbols"][s].get("contract") or {}) for s in symbols}
    rep = dd.build_report(raw, contracts, hashes)
    if rep["blockers"]:
        raise ProtocolError("E14 engeli (koşu anında): " + "; ".join(rep["blockers"]))
    meta = {"health_report_sha256": dd.file_sha256(hp), "file_sha256": hashes,
            "common_holdout_end": rep["common_holdout_end"],
            "symbols": {s: {k: rep["symbols"][s][k] for k in
                            ("listing_day", "first_day", "last_day", "missing_after_listing",
                             "warmup_55_bar_done")} for s in symbols}}
    return daily, meta, rep


# ----------------------------------------------------------------- metrikler / kapılar
def capital_exhausted(res: PBResult, initial: float) -> bool:
    """E16: gerçekleşmiş bakiye dönem içinde ≤ 0 oldu mu (işlem kapanış sırasıyla)."""
    bal = initial
    for t in sorted(res.trades, key=lambda t: t.exit_day):
        bal += t.pnl
        if bal <= 0:
            return True
    return res.counters.get("entries_blocked_no_capital", 0) > 0


def metrics(res: PBResult, p: PlanBParams) -> dict:
    tr = res.trades
    by_year, by_sym, reasons = {}, {}, {}
    for t in tr:
        y = str(dd.day_date(t.exit_day).year)
        for key, store in ((y, by_year), (t.symbol, by_sym)):
            d = store.setdefault(key, {"trades": 0, "gp": 0.0, "gl": 0.0, "net": 0.0})
            d["trades"] += 1
            d["net"] += t.pnl
            d["gp" if t.pnl > 0 else "gl"] += abs(t.pnl)
        reasons[t.reason] = reasons.get(t.reason, 0) + 1
    for store in (by_year, by_sym):
        for d in store.values():
            d["pf"] = (d["gp"] / d["gl"]) if d["gl"] > 0 else (float("inf") if d["gp"] > 0 else 0.0)
            d["net"] = round(d["net"], 2)
            del d["gp"], d["gl"]
    return {
        "total_trades": len(tr),
        "profit_factor": res.profit_factor,
        "max_drawdown": res.max_drawdown,
        "initial_balance": p.initial_balance,
        "final_equity": res.final_balance,
        "net_pnl": sum(t.pnl for t in tr),
        "expectancy_r": float(np.mean([t.pnl_r for t in tr])) if tr else 0.0,
        "win_rate": (sum(1 for t in tr if t.pnl > 0) / len(tr)) if tr else 0.0,
        "total_fees": sum(t.entry_fee + t.exit_fee for t in tr),
        "total_funding": sum(t.funding for t in tr),
        "exit_reasons": reasons,
        "capital_exhausted": capital_exhausted(res, p.initial_balance),
        "counters": res.counters,
        "missing_day_valuations": res.missing_day_valuations,
        "by_year": by_year,
        "by_symbol": by_sym,
    }


def evaluate(m: dict, phase: str, gates: dict | None = None) -> dict:
    g = gates or (INSAMPLE_GATES if phase == "insample" else HOLDOUT_GATES)
    res = {f"PF > {g['min_pf']}": bool(m["profit_factor"] > g["min_pf"])}
    if "min_trades" in g:
        res[f"işlem >= {g['min_trades']}"] = bool(m["total_trades"] >= g["min_trades"])
    res[f"DD < %{g['max_dd']*100:.0f}"] = bool(m["max_drawdown"] < g["max_dd"])
    res["sermaye tükenmedi (E16)"] = not bool(m["capital_exhausted"])
    return {"gates": res, "passed": all(res.values())}


def _num_back(x):
    if x == "inf":
        return float("inf")
    if x == "nan":
        return float("nan")
    return float(x)


def _recompute_pass(prev: dict, gates: dict) -> bool:
    """Kapılar raporun SAYILARINDAN ve koddaki (rapordaki değil) eşiklerden yeniden hesaplanır."""
    m = prev["metrics"]
    return evaluate({"profit_factor": _num_back(m["profit_factor"]),
                     "total_trades": int(m["total_trades"]),
                     "max_drawdown": _num_back(m["max_drawdown"]),
                     "capital_exhausted": bool(m["capital_exhausted"])},
                    "insample", gates)["passed"]


def _protocol_config(symbols, periods, p: PlanBParams, gates_ins, gates_ho) -> dict:
    return _clean({
        "symbols": list(symbols), "periods": dataclasses.asdict(periods),
        "engine": dataclasses.asdict(p),
        "strategy": {"entry_lookback": sb.ENTRY_LOOKBACK, "exit_lookback": sb.EXIT_LOOKBACK,
                     "atr_period": sb.ATR_PERIOD},
        "data": {"max_missing_ratio": dd.MAX_MISSING_RATIO},
        "gates": {"insample": gates_ins, "holdout": gates_ho},
    })


# ----------------------------------------------------------------- koşu
def run_protocol(phase: str, data_dir: Path, report_dir: Path,
                 symbols=SYMBOLS, periods: Periods = Periods(),
                 p: PlanBParams = PlanBParams(), root: Path = ROOT,
                 _allow_custom: bool = False, _gates: dict | None = None) -> dict:
    """`_allow_custom` ve `_gates` yalnız testler içindir; CLI hiçbir zaman açmaz."""
    if phase not in ("insample", "holdout"):
        raise ProtocolError("phase: insample | holdout")
    if not _allow_custom and (tuple(symbols) != SYMBOLS or periods != Periods()
                              or p != PlanBParams() or _gates is not None):
        raise ProtocolError("Üretim protokolünde semboller, dönemler, parametreler ve kapılar "
                            "SABİT (varsayılanlar); değiştirilemez.")
    gates_ins = (_gates or {}).get("insample", INSAMPLE_GATES)
    gates_ho = (_gates or {}).get("holdout", HOLDOUT_GATES)
    report_dir.mkdir(parents=True, exist_ok=True)
    ins_path, ho_path = report_dir / INSAMPLE_FILE, report_dir / HOLDOUT_FILE
    out_path = ins_path if phase == "insample" else ho_path
    lock_path = out_path.with_suffix(".lock")
    fp = code_fingerprint(root)
    cfg = _protocol_config(symbols, periods, p, gates_ins, gates_ho)

    prev_ins = None
    if phase == "insample":
        if ins_path.exists() or lock_path.exists():
            raise ProtocolError(f"{INSAMPLE_FILE}/kilit zaten var: TEK ATIŞ kullanıldı. Yeniden "
                                "koşmak = yeni versiyon (Plan B.1) + yeni tek atış. Dosyaları silme.")
    else:
        if ho_path.exists() or lock_path.exists():
            raise ProtocolError(f"{HOLDOUT_FILE}/kilit zaten var: hold-out TEK ATIŞ kullanıldı.")
        if not ins_path.exists():
            raise ProtocolError(f"Önce in-sample koşulmalı ({INSAMPLE_FILE} yok).")
        prev_ins = json.loads(ins_path.read_text(encoding="utf-8"))
        if not verify_seal(prev_ins):
            raise ProtocolError("In-sample raporu bütünlük mührüyle uyuşmuyor (elle değiştirilmiş).")
        if _recompute_pass(prev_ins, gates_ins) != bool(prev_ins.get("gates_passed")):
            raise ProtocolError("In-sample raporu kendi içinde tutarsız (kapılar yeniden hesaplanamadı).")
        if not _recompute_pass(prev_ins, gates_ins):
            raise ProtocolError("Plan B in-sample kapılarında KALDI: Plan B REDDEDİLDİ, hold-out koşulmaz.")
        if prev_ins.get("code_fingerprint") != fp:
            raise ProtocolError("Kod/spesifikasyon in-sample'dan beri DEĞİŞMİŞ (parmak izi uyuşmuyor). "
                                "Kural değişikliği = yeni versiyon + yeni tek atış.")
        if prev_ins.get("protocol_config") != cfg:
            raise ProtocolError("Semboller/dönemler/parametreler/kapılar in-sample'dan farklı.")

    daily, data_meta, _ = load_and_check_data(data_dir, report_dir, symbols)
    ins_end = _day(periods.insample_end)
    slice_hashes = {s: _frame_rows_hash(daily[s][daily[s].index <= ins_end]) for s in symbols}

    if phase == "insample":
        start, end = _day(periods.insample_start), ins_end
    else:
        if prev_ins["slice_hashes"] != slice_hashes:
            raise ProtocolError("In-sample veri dilimi in-sample'dan beri DEĞİŞMİŞ.")
        start = _day(periods.holdout_start)
        end = min(int(daily[s].index[-1]) for s in symbols)     # E13 ortak bitiş
        if end < start:
            raise ProtocolError("hold-out için yeterli veri yok")

    # ---- git durumu: kilit ve rapor oluşmadan ÖNCE
    git = git_state(root)

    # ---- tüm doğrulamalar geçti: TEK ATIŞ HAKKI BURADA TÜKETİLİR (koşudan önce, atomik)
    _acquire_lock(lock_path)

    frames = {s: sb.compute_signals(daily[s][daily[s].index <= end]) for s in symbols}
    res = run_portfolio(frames, start, end, p, priority=symbols)
    m = metrics(res, p)
    verdict = evaluate(m, phase, gates_ins if phase == "insample" else gates_ho)

    report = {
        "version": VERSION, "phase": phase,
        "run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "period": {"start": str(dd.day_date(start)), "end_inclusive": str(dd.day_date(end))},
        "gate_thresholds": gates_ins if phase == "insample" else gates_ho,
        "gates": verdict["gates"], "gates_passed": verdict["passed"],
        "verdict": "GEÇTİ" if verdict["passed"] else "KALDI",
        "metrics": m,
        "data": data_meta,
        "slice_hashes": slice_hashes,
        "code_fingerprint": fp,
        "protocol_config": cfg,
        "git": git,
        "env": {"python": platform.python_version(), "pandas": pd.__version__,
                "numpy": np.__version__},
        "notes": [E13_NOTE],
        "insample_reference": ({"verdict": prev_ins["verdict"], "run_utc": prev_ins["run_utc"]}
                               if prev_ins else None),
    }
    report = seal(_clean(report))
    tmp = out_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, out_path)
    out_path.with_suffix(".md").write_text(render_markdown(report), encoding="utf-8")
    return report


def render_markdown(r: dict) -> str:
    m = r["metrics"]
    ph = "IN-SAMPLE (2020-2024)" if r["phase"] == "insample" else "HOLD-OUT (2025+)"
    L = [f"# Plan B v1 — {ph}: **{r['verdict']}**", "",
         f"Koşu: {r['run_utc']} · Dönem: {r['period']['start']} → {r['period']['end_inclusive']} (dahil)",
         "", "## Kapılar (önceden sabit, E9 + E16)"]
    for k, ok in r["gates"].items():
        L.append(f"- {'✅' if ok else '❌'} {k}")
    L += ["", "## Portföy sonucu (BTC/ETH/SOL/BNB ortak hesap, maliyetler + funding dahil)",
          f"- Profit factor: **{m['profit_factor']}**",
          f"- İşlem sayısı: **{m['total_trades']}**",
          f"- Max drawdown (günlük MTM, E15): **%{float(m['max_drawdown'])*100:.2f}**",
          f"- Beklenti: {float(m['expectancy_r']):.3f} R · Kazanma oranı: %{float(m['win_rate'])*100:.1f}",
          f"- Başlangıç → bitiş: {m['initial_balance']:.0f} → {float(m['final_equity']):.0f} "
          f"(net {float(m['net_pnl']):.2f})",
          f"- Ücretler: {float(m['total_fees']):.2f} · Funding: {float(m['total_funding']):.2f}",
          f"- Çıkış sebepleri: {m['exit_reasons']}",
          f"- Sayaçlar: {m['counters']}",
          f"- Eksik günde değerleme (E12): {m['missing_day_valuations']}",
          "", "## Yıl bazında (kapanış yılı; bilgi amaçlı, kapı değil)",
          "| Yıl | İşlem | PF | Net $ |", "|---|---:|---:|---:|"]
    for y in sorted(m["by_year"]):
        d = m["by_year"][y]
        L.append(f"| {y} | {d['trades']} | {d['pf']} | {d['net']} |")
    L += ["", "## Sembol bazında (bilgi amaçlı)", "| Sembol | İşlem | PF | Net $ |", "|---|---:|---:|---:|"]
    for s in sorted(m["by_symbol"]):
        d = m["by_symbol"][s]
        L.append(f"| {s} | {d['trades']} | {d['pf']} | {d['net']} |")
    g = r["git"]
    L += ["", "## Tekrar üretilebilirlik",
          f"- Kod parmak izi: `{r['code_fingerprint'][:16]}…` · git: {g.get('commit')}",
          f"- Kilit öncesi değişmiş dosyalar: {g.get('changed_files_before_lock')}",
          f"- Veri sha256 (sağlık raporuyla aynı): " +
          ", ".join(f"{s} `{h[:12]}…`" for s, h in r["data"]["file_sha256"].items()),
          f"- Python {r['env']['python']}, pandas {r['env']['pandas']}", "",
          "## Notlar"] + [f"- {n}" for n in r["notes"]] + [
          "", "> Kural: sonuç kapılarla raporlanır, süslenmez. KALDI ise Plan B v1 REDDEDİLDİ, "
          "parametre kurcalanmaz."]
    return "\n".join(L) + "\n"
