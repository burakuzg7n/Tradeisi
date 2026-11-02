"""V3 tek atış protokolü (docs/V3_SPEC_TASLAK.md §2, §6–§7).

TEK ATIŞ KURALLARI (kod ile zorlanır):
- insample: yalnız BİR kez (reports/V3_INSAMPLE.json veya .lock varsa reddeder).
- holdout: yalnız in-sample GEÇTİYSE; mühür, kapılar (KODDAKİ eşiklerle yeniden hesap),
  parmak izi, yapılandırma ve in-sample veri dilimi değişmediyse; bir kez.
- Tüm doğrulamalar (veri hash'leri, E14-benzeri engeller, 15m hizalama/tekillik,
  dönem sonu) kilitten ÖNCE; git durumu kilit ve rapordan ÖNCE; kilit koşudan ÖNCE.
- Parametreler/kapılar sabit; optimize edilmez.

Sunuş: sonuç "yeni sembollerde önceden kaydedilmiş test"tir; tam bağımsız piyasa
kanıtı değildir (§2). DD 15m kapanış MTM'sinden ölçülür; %30 bir durma garantisi
değildir. HAC testi %80 gücü garanti etmez (§6a).

Güvenlik notu: kilitler yerel dosyalara dayanır; dosya silmek / başka report_dir /
kod değiştirmek kodla ENGELLENEMEZ. Gerçek güvence: sonucun HEMEN commit'i ve
bağımsız denetim (AGENTS.md).
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import os
import platform
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import daily_data as dd
from . import strategy_v3 as sv
from . import v3_data as vd
from .engine_v3 import V3Params, V3Result, newey_west_t, run_v3
from .protocol_planb import git_state
from .protocol_v2 import _acquire_lock, _clean, _norm_bytes, seal, verify_seal

ROOT = Path(__file__).resolve().parents[1]
VERSION = "V3"
SYMBOLS = vd.SYMBOLS
INSAMPLE_FILE = "V3_INSAMPLE.json"
HOLDOUT_FILE = "V3_HOLDOUT.json"
HEALTH_FILE = "V3_VERI_SAGLIK.json"

# §7 — DEĞİŞTİRİLEMEZ (Z1 = %30 DD ve Z2 = %1 risk Burak kararı, [SAPMA])
INSAMPLE_GATES = {"min_pf": 1.3, "min_trades": 1300, "min_mean": 0.0, "min_t": 2.0, "max_dd": 0.30}
HOLDOUT_GATES = {"min_pf": 1.15, "min_mean": 0.0, "max_dd": 0.30}

_FINGERPRINT_FILES = (
    "tradebot/strategy_v3.py", "tradebot/engine_v3.py", "tradebot/v3_data.py",
    "tradebot/daily_data.py", "tradebot/protocol_v3.py", "tradebot/protocol_v2.py",
    "tradebot/protocol_planb.py", "docs/V3_SPEC_TASLAK.md",
)

NOTES = [
    "Sunuş (§2): yeni sembollerde önceden kaydedilmiş test; tam bağımsız piyasa kanıtı değildir.",
    "DD 15 dakikalık kapanış MTM equity'sinden ölçülür; mum içi en kötü an görünmez. "
    "%30 DD sınırı gerçek işlemde bir durma garantisi değildir.",
    "İstatistik ölçütü günlük seri r_d (tüm günler) üzerinde Newey–West HAC t'dir; %80 "
    "gücü garanti etmez. 1.300 işlem bir kapsam kararıdır.",
    "Maliyet modeli (slippage %0,03, funding %0,01/an) sabit varsayımdır; üst sınır değildir.",
]


class ProtocolError(RuntimeError):
    """Protokol kuralı ihlali: koşu reddedilir."""


@dataclasses.dataclass(frozen=True)
class Periods:
    insample_start: str = str(vd.INSAMPLE_START)
    insample_end: str = str(vd.INSAMPLE_END)
    holdout_start: str = str(vd.HOLDOUT_START)


def _d(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def code_fingerprint(root: Path = ROOT) -> str:
    h = hashlib.sha256()
    for rel in _FINGERPRINT_FILES:
        h.update(rel.encode())
        h.update(_norm_bytes(root / rel))
    return h.hexdigest()


def _rows_hash(df: pd.DataFrame) -> str:
    h = hashlib.sha256()
    h.update(np.ascontiguousarray(df.index.to_numpy(dtype="int64")).tobytes())
    h.update(np.ascontiguousarray(df[["open", "high", "low", "close"]].to_numpy(dtype="float64")).tobytes())
    return h.hexdigest()


def load_and_check_data(data_dir: Path, report_dir: Path, symbols, periods: Periods):
    hp = report_dir / HEALTH_FILE
    if not hp.exists():
        raise ProtocolError(f"{HEALTH_FILE} yok: önce veri indirilip sağlık raporu üretilmeli.")
    health = json.loads(hp.read_text(encoding="utf-8"))
    if health.get("verdict") != "VERİ UYGUN":
        raise ProtocolError(f"Sağlık raporu: {health.get('verdict')}. Koşu yapılmaz.")
    raw, bars, hashes = {}, {}, {}
    for s in symbols:
        p = data_dir / f"{s}_15m.csv"
        if not p.exists():
            raise ProtocolError(f"[{s}] veri yok: {p.name}")
        hashes[s] = dd.file_sha256(p)
        if hashes[s] != (health.get("symbols", {}).get(s) or {}).get("file_sha256"):
            raise ProtocolError(f"[{s}] {p.name} sha256 sağlık raporundakiyle AYNI DEĞİL.")
        raw[s] = dd.load_daily_raw(p)
        try:
            bars[s] = vd.load_15m(p)          # hizasız / tekrar / sırasız → kilitten ÖNCE ret
        except ValueError as e:
            raise ProtocolError(f"[{s}] veri biçimi: {e}")
    contracts = {s: (health["symbols"][s].get("contract") or {}) for s in symbols}
    rep = vd.build_report(raw, contracts, hashes,
                          insample=(_d(periods.insample_start), _d(periods.insample_end)),
                          holdout_start=_d(periods.holdout_start))
    if rep["blockers"]:
        raise ProtocolError("Veri engeli (koşu anında): " + "; ".join(rep["blockers"]))
    meta = {"health_report_sha256": dd.file_sha256(hp), "file_sha256": hashes,
            "d_son": rep["d_son"],
            "symbols": {s: {k: rep["symbols"][s][k] for k in ("listing", "first_bar", "last_bar")}
                        for s in symbols}}
    return bars, meta, rep


def metrics(res: V3Result, p: V3Params) -> dict:
    tr = res.trades
    r_d = res.daily_returns(p.initial_balance)
    m, se, L, t = newey_west_t(r_d.to_numpy())
    r_daily_R = pd.Series(0.0, index=r_d.index)
    for x in tr:
        r_daily_R.loc[x.acct_day] += x.r
    by_year, by_sym, reasons = {}, {}, {}
    for x in tr:
        y = str(dd.day_date(x.acct_day).year)
        for key, store in ((y, by_year), (x.symbol, by_sym)):
            d = store.setdefault(key, {"trades": 0, "gp": 0.0, "gl": 0.0, "net": 0.0})
            d["trades"] += 1
            d["net"] += x.pnl
            d["gp" if x.pnl > 0 else "gl"] += abs(x.pnl)
        reasons[x.reason] = reasons.get(x.reason, 0) + 1
    for store in (by_year, by_sym):
        for d in store.values():
            d["pf"] = (d["gp"] / d["gl"]) if d["gl"] > 0 else (float("inf") if d["gp"] > 0 else 0.0)
            d["net"] = round(d["net"], 2)
            del d["gp"], d["gl"]
    return {
        "total_trades": len(tr),
        "longs": sum(1 for x in tr if x.side == "long"),
        "shorts": sum(1 for x in tr if x.side == "short"),
        "profit_factor": res.profit_factor,
        "max_drawdown": res.max_drawdown,
        "initial_balance": p.initial_balance,
        "final_equity": float(res.equity.iloc[-1]) if res.equity is not None and len(res.equity) else p.initial_balance,
        "net_pnl": sum(x.pnl for x in tr),
        "expectancy_r": float(np.mean([x.r for x in tr])) if tr else 0.0,
        "win_rate": (sum(1 for x in tr if x.pnl > 0) / len(tr)) if tr else 0.0,
        "total_fees": sum(x.entry_fee + x.exit_fee for x in tr),
        "total_funding": sum(x.funding for x in tr),
        "daily": {"days": int(len(r_d)), "mean": m, "hac_se": se, "hac_lag": L, "hac_t": t,
                  "mean_R_per_day_info": float(r_daily_R.mean()) if len(r_daily_R) else 0.0},
        "exit_reasons": reasons,
        "counters": res.counters,
        "capital_exhausted": bool(res.capital_exhausted),
        "by_year": by_year,
        "by_symbol": by_sym,
    }


def evaluate(m: dict, phase: str, gates: dict | None = None) -> dict:
    g = gates or (INSAMPLE_GATES if phase == "insample" else HOLDOUT_GATES)
    d = m["daily"]
    mean = float(d["mean"])
    res = {f"PF > {g['min_pf']}": bool(m["profit_factor"] > g["min_pf"])}
    if "min_trades" in g:
        res[f"işlem >= {g['min_trades']}"] = bool(m["total_trades"] >= g["min_trades"])
    res[f"günlük ortalama > {g['min_mean']}"] = bool(mean > g["min_mean"])
    if "min_t" in g:
        t = float(d["hac_t"])
        res[f"HAC t > {g['min_t']} (nan → KALDI)"] = bool(math.isfinite(t) and t > g["min_t"])
    res[f"DD < %{g['max_dd']*100:.0f}"] = bool(m["max_drawdown"] < g["max_dd"])
    res["sermaye tükenmedi"] = not bool(m["capital_exhausted"])
    return {"gates": res, "passed": all(res.values())}


def _num(x):
    if x == "inf":
        return float("inf")
    if x == "nan":
        return float("nan")
    return float(x)


def _recompute_pass(prev: dict, gates: dict) -> bool:
    m = prev["metrics"]
    d = m["daily"]
    return evaluate({"profit_factor": _num(m["profit_factor"]), "total_trades": int(m["total_trades"]),
                     "max_drawdown": _num(m["max_drawdown"]),
                     "capital_exhausted": bool(m["capital_exhausted"]),
                     "daily": {"mean": _num(d["mean"]), "hac_t": _num(d["hac_t"])}},
                    "insample", gates)["passed"]


def _protocol_config(symbols, periods, p, gi, gh) -> dict:
    return _clean({"symbols": list(symbols), "periods": dataclasses.asdict(periods),
                   "engine": dataclasses.asdict(p),
                   "strategy": {"asia_slots": [0, 27], "trigger_slots": [28, 79],
                                "min_valid_bars": sv.MIN_VALID_BARS, "sma_n": sv.SMA_N,
                                "min_stop": sv.MIN_STOP, "rr": sv.RR},
                   "data": {"max_missing_ratio": vd.MAX_MISSING_RATIO},
                   "gates": {"insample": gi, "holdout": gh}})


def run_protocol(phase: str, data_dir: Path, report_dir: Path, symbols=SYMBOLS,
                 periods: Periods = Periods(), p: V3Params = V3Params(), root: Path = ROOT,
                 _allow_custom: bool = False, _gates: dict | None = None) -> dict:
    """`_allow_custom` ve `_gates` yalnız testler içindir; CLI hiçbir zaman açmaz."""
    if phase not in ("insample", "holdout"):
        raise ProtocolError("phase: insample | holdout")
    if not _allow_custom and (tuple(symbols) != SYMBOLS or periods != Periods()
                              or p != V3Params() or _gates is not None):
        raise ProtocolError("Üretim protokolünde semboller, dönemler, parametreler ve kapılar "
                            "SABİT; değiştirilemez.")
    gi = (_gates or {}).get("insample", INSAMPLE_GATES)
    gh = (_gates or {}).get("holdout", HOLDOUT_GATES)
    report_dir.mkdir(parents=True, exist_ok=True)
    ins_path, ho_path = report_dir / INSAMPLE_FILE, report_dir / HOLDOUT_FILE
    out_path = ins_path if phase == "insample" else ho_path
    lock_path = out_path.with_suffix(".lock")
    fp = code_fingerprint(root)
    cfg = _protocol_config(symbols, periods, p, gi, gh)

    prev = None
    if phase == "insample":
        if ins_path.exists() or lock_path.exists():
            raise ProtocolError(f"{INSAMPLE_FILE}/kilit zaten var: TEK ATIŞ kullanıldı. "
                                "Yeniden koşmak = yeni versiyon (V3.1) + yeni tek atış.")
    else:
        if ho_path.exists() or lock_path.exists():
            raise ProtocolError(f"{HOLDOUT_FILE}/kilit zaten var: hold-out TEK ATIŞ kullanıldı.")
        if not ins_path.exists():
            raise ProtocolError(f"Önce in-sample koşulmalı ({INSAMPLE_FILE} yok).")
        prev = json.loads(ins_path.read_text(encoding="utf-8"))
        if not verify_seal(prev):
            raise ProtocolError("In-sample raporu bütünlük mührüyle uyuşmuyor (elle değiştirilmiş).")
        if _recompute_pass(prev, gi) != bool(prev.get("gates_passed")):
            raise ProtocolError("In-sample raporu kendi içinde tutarsız (kapılar yeniden hesaplanamadı).")
        if not _recompute_pass(prev, gi):
            raise ProtocolError("V3 in-sample kapılarında KALDI: V3 REDDEDİLDİ, hold-out koşulmaz.")
        if prev.get("code_fingerprint") != fp:
            raise ProtocolError("Kod/spesifikasyon in-sample'dan beri DEĞİŞMİŞ (parmak izi uyuşmuyor).")
        if prev.get("protocol_config") != cfg:
            raise ProtocolError("Semboller/dönemler/parametreler/kapılar in-sample'dan farklı.")

    bars, data_meta, health_now = load_and_check_data(data_dir, report_dir, symbols, periods)
    ins_end_excl = (vd.day_index(_d(periods.insample_end)) + 1) * vd.DAY_MS
    slice_hashes = {s: _rows_hash(bars[s][bars[s].index < ins_end_excl]) for s in symbols}

    if phase == "insample":
        start = vd.day_index(_d(periods.insample_start))
        end = vd.day_index(_d(periods.insample_end))
    else:
        if prev["slice_hashes"] != slice_hashes:
            raise ProtocolError("In-sample veri dilimi in-sample'dan beri DEĞİŞMİŞ.")
        start = vd.day_index(_d(periods.holdout_start))
        if not health_now["d_son"]:
            raise ProtocolError("d_son yok")
        end = vd.day_index(_d(health_now["d_son"]))
        if end < start:
            raise ProtocolError("hold-out için yeterli veri yok")

    git = git_state(root)                      # kilit ve rapordan ÖNCE
    _acquire_lock(lock_path)                   # TEK ATIŞ HAKKI BURADA TÜKETİLİR

    cut = (end + 1) * vd.DAY_MS
    cut_bars = {s: bars[s][bars[s].index < cut] for s in symbols}
    intents = {s: sv.generate_intents(s, cut_bars[s], start, end) for s in symbols}
    res = run_v3(cut_bars, intents, start, end, p)
    m = metrics(res, p)
    verdict = evaluate(m, phase, gi if phase == "insample" else gh)
    archive = _write_archive(res, p, out_path)

    report = {
        "version": VERSION, "phase": phase,
        "run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "period": {"start": str(dd.day_date(start)), "end_inclusive": str(dd.day_date(end))},
        "gate_thresholds": gi if phase == "insample" else gh,
        "gates": verdict["gates"], "gates_passed": verdict["passed"],
        "verdict": "GEÇTİ" if verdict["passed"] else "KALDI",
        "metrics": m, "archive": archive, "data": data_meta, "slice_hashes": slice_hashes,
        "code_fingerprint": fp, "protocol_config": cfg, "git": git,
        "env": {"python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__},
        "notes": NOTES,
        "insample_reference": ({"verdict": prev["verdict"], "run_utc": prev["run_utc"]} if prev else None),
    }
    report = seal(_clean(report))
    tmp = out_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, out_path)
    out_path.with_suffix(".md").write_text(render_markdown(report), encoding="utf-8")
    return report


def _write_archive(res: V3Result, p: V3Params, out_path: Path) -> dict:
    """Ham sonuç arşivi (bağımsız yeniden hesap için): tüm işlemler, günlük seri, 15m
    equity yolu. Dosyaların sha256'ları mühürlü rapora yazılır."""
    stem = out_path.with_suffix("")
    files = {
        "trades": stem.with_name(stem.name + "_islemler.csv"),
        "daily": stem.with_name(stem.name + "_gunluk.csv"),
        "equity": stem.with_name(stem.name + "_equity.csv"),
    }
    pd.DataFrame([dataclasses.asdict(t) | {"r": t.r} for t in res.trades],
                 columns=[f.name for f in dataclasses.fields(res.trades[0])] + ["r"]
                 if res.trades else None).to_csv(files["trades"], index=False)
    r_d = res.daily_returns(p.initial_balance)
    pd.DataFrame({"day": r_d.index, "date": [str(dd.day_date(d)) for d in r_d.index],
                  "r_d": r_d.to_numpy()}).to_csv(files["daily"], index=False)
    eq = res.equity if res.equity is not None else pd.Series(dtype=float)
    pd.DataFrame({"ts": eq.index, "equity": eq.to_numpy()}).to_csv(files["equity"], index=False)
    return {k: {"file": v.name, "sha256": dd.file_sha256(v)} for k, v in files.items()}


def render_markdown(r: dict) -> str:
    m, d = r["metrics"], r["metrics"]["daily"]
    ph = "IN-SAMPLE (2021-2024)" if r["phase"] == "insample" else "HOLD-OUT (2025+)"
    L = [f"# V3 — {ph}: **{r['verdict']}**", "",
         f"Koşu: {r['run_utc']} · Dönem: {r['period']['start']} → {r['period']['end_inclusive']} (dahil)",
         "", "## Kapılar (önceden sabit, spec §7)"]
    for k, ok in r["gates"].items():
        L.append(f"- {'✅' if ok else '❌'} {k}")
    L += ["", "## Portföy (XRP/DOGE/ADA/AVAX/LINK, ortak hesap, %1 risk, maliyetler dahil)",
          f"- Profit factor: **{m['profit_factor']}**",
          f"- İşlem: **{m['total_trades']}** (long {m['longs']} / short {m['shorts']})",
          f"- Max DD (15m MTM): **%{float(m['max_drawdown'])*100:.2f}**",
          f"- Günlük seri: {d['days']} gün, ortalama {float(d['mean']):.6f}, HAC SE {float(d['hac_se']):.6f} "
          f"(L={d['hac_lag']}), **t = {d['hac_t']}**",
          f"- Beklenti {float(m['expectancy_r']):.3f} R · kazanma %{float(m['win_rate'])*100:.1f} · "
          f"günlük ortalama R (bilgi) {float(d['mean_R_per_day_info']):.4f}",
          f"- {m['initial_balance']:.0f} → {float(m['final_equity']):.0f} (net {float(m['net_pnl']):.2f}) · "
          f"ücret {float(m['total_fees']):.2f} · funding {float(m['total_funding']):.2f}",
          f"- Çıkışlar: {m['exit_reasons']}", f"- Sayaçlar: {m['counters']}",
          f"- Sermaye tükendi: {m['capital_exhausted']}",
          "", "## Yıl (muhasebe günü yılı; bilgi, kapı değil)", "| Yıl | İşlem | PF | Net $ |", "|---|---:|---:|---:|"]
    for y in sorted(m["by_year"]):
        x = m["by_year"][y]
        L.append(f"| {y} | {x['trades']} | {x['pf']} | {x['net']} |")
    L += ["", "## Sembol (bilgi)", "| Sembol | İşlem | PF | Net $ |", "|---|---:|---:|---:|"]
    for s in sorted(m["by_symbol"]):
        x = m["by_symbol"][s]
        L.append(f"| {s} | {x['trades']} | {x['pf']} | {x['net']} |")
    g = r["git"]
    L += ["", "## Tekrar üretilebilirlik",
          f"- Parmak izi `{r['code_fingerprint'][:16]}…` · git {g.get('commit')}",
          f"- Kilit öncesi değişmiş dosyalar: {g.get('changed_files_before_lock')}",
          "- Veri sha256: " + ", ".join(f"{s} `{h[:12]}…`" for s, h in r["data"]["file_sha256"].items()),
          f"- Python {r['env']['python']}, pandas {r['env']['pandas']}",
          "- Ham sonuç arşivi (sha256 mühürlü raporda): " +
          ", ".join(f"`{a['file']}`" for a in r["archive"].values()), "", "## Notlar"]
    L += [f"- {n}" for n in r["notes"]]
    L += ["", "> Kural: sonuç kapılarla raporlanır, süslenmez. KALDI ise V3 REDDEDİLDİ, parametre "
          "kurcalanmaz. GEÇTİ tek başına canlıya geçiş hakkı vermez (docs/V3_DOGRULAMA_PLANI.md)."]
    return "\n".join(L) + "\n"
