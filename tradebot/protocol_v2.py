"""V2 test protokolü (DEVIR_NOTU §8 + docs/SPEC_EKLERI.md E1-E4, E3b, E3c).

TEK ATIŞ KURALLARI (kod ile zorlanır):
- insample: yalnız BİR kez koşar. reports/V2_INSAMPLE.json varsa reddeder.
  Yeniden koşmak = yeni versiyon (V2.1) + yeni tek atış; bu dosya elle silinmez.
- holdout: yalnız in-sample GEÇTİYSE, kod parmak izi ve in-sample veri dilimi
  DEĞİŞMEDİYSE ve daha önce koşmadıysa çalışır.
- Strateji parametreleri bu modülde OPTİMİZE EDİLMEZ; varsayılanlar config.py'den.

Dönemler: in-sample 2020-01-01 → 2025-01-01 (hariç); hold-out 2025-01-01 → verinin
son tam günü. Gösterge/yapı ısınması önceki veriyle yapılır (E3c); dönem başında
yeni sermaye, boş pozisyon. Dönem sonunda açık pozisyon zorla kapanır (E3b).
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import platform
import subprocess
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .backtest import Backtester, BacktestResult
from .config import BacktestParams, StrategyParams
from .data import load_csv
from .strategy_v2 import generate_orders_v2

ROOT = Path(__file__).resolve().parents[1]
VERSION = "V2"
SYMBOLS = ("BTCUSDT", "ETHUSDT")
INSAMPLE_FILE = "V2_INSAMPLE.json"
HOLDOUT_FILE = "V2_HOLDOUT.json"

# Kapı eşikleri (DEVIR_NOTU §8 + SPEC_EKLERI E3/E4) — DEĞİŞTİRİLEMEZ
INSAMPLE_GATES = {"min_pf": 1.3, "min_trades": 150, "max_dd": 0.15}
HOLDOUT_GATES = {"min_pf": 1.15, "max_dd": 0.15}

# Sonucu belirleyen kod modülleri (parmak izi): değişirse hold-out reddedilir
_FINGERPRINT_MODULES = (
    "backtest", "config", "data", "sessions", "strategy",
    "strategy_v2", "structure", "protocol_v2",
)


class ProtocolError(RuntimeError):
    """Protokol kuralı ihlali: koşu reddedilir."""


@dataclass(frozen=True)
class Periods:
    insample_start: str = "2020-01-01"
    insample_end_excl: str = "2025-01-01"
    holdout_start: str = "2025-01-01"


# ----------------------------------------------------------------- yardımcılar
def _norm_bytes(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def code_fingerprint(root: Path = ROOT) -> str:
    h = hashlib.sha256()
    files = [root / "tradebot" / f"{m}.py" for m in _FINGERPRINT_MODULES]
    files.append(root / "docs" / "SPEC_EKLERI.md")
    for f in files:
        h.update(f.name.encode())
        h.update(_norm_bytes(f))
    return h.hexdigest()


def frame_hash(df: pd.DataFrame) -> str:
    h = hashlib.sha256()
    h.update(np.ascontiguousarray(df.index.asi8).tobytes())
    cols = df[["open", "high", "low", "close", "volume"]].to_numpy(dtype="float64")
    h.update(np.ascontiguousarray(cols).tobytes())
    return h.hexdigest()


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def data_report(df: pd.DataFrame, freq: str) -> dict:
    idx = df.index
    expected = pd.date_range(idx[0], idx[-1], freq=freq)
    miss = expected.difference(idx)
    step = pd.Timedelta(freq)
    gaps: list[list] = []          # [başlangıç, bitiş, bar sayısı]
    for t in miss:
        if gaps and t - gaps[-1][1] == step:
            gaps[-1][1] = t
            gaps[-1][2] += 1
        else:
            gaps.append([t, t, 1])
    return {
        "first": str(idx[0]), "last": str(idx[-1]),
        "bars": int(len(idx)), "missing_bars": int(len(miss)),
        "gap_count": len(gaps),
        "max_gap_bars": max((g[2] for g in gaps), default=0),
        "gaps": [{"start": str(g[0]), "bars": g[2]} for g in gaps],
    }


def last_full_day_end(ltf: pd.DataFrame, bar_minutes: int = 15) -> pd.Timestamp:
    """Verideki son TAM günün bitişi (hariç sınır). Kısmi gün dışarıda kalır."""
    last = ltf.index[-1]
    day = last.floor("D")
    nxt = day + pd.Timedelta(days=1)
    return nxt if last + pd.Timedelta(minutes=bar_minutes) >= nxt else day


def _git_info() -> dict:
    def run(*a):
        return subprocess.run(
            ["git", *a], cwd=ROOT, capture_output=True, text=True, timeout=10
        ).stdout.strip()
    try:
        return {"commit": run("rev-parse", "HEAD") or None,
                "dirty": bool(run("status", "--porcelain"))}
    except Exception:
        return {"commit": None, "dirty": None}


def _num(x):
    """JSON için: inf/nan güvenli sayı."""
    if isinstance(x, (np.floating, np.integer)):
        x = x.item()
    if isinstance(x, float) and not math.isfinite(x):
        return "inf" if x > 0 else "nan"
    return x


def _clean(obj):
    """Rekürsif: numpy → python, inf/nan → 'inf'/'nan' (standart JSON)."""
    if isinstance(obj, dict):
        return {str(k): _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    return _num(obj)


# ----------------------------------------------------------------- çekirdek
def run_period(
    ltf: pd.DataFrame,
    htf: pd.DataFrame,
    start: str,
    end_excl: pd.Timestamp | str,
    sp: StrategyParams,
    bp: BacktestParams,
) -> tuple[BacktestResult, dict]:
    """Tek sembol, tek dönem. Veri `end_excl`'den sonrası KESİLİR (lookahead yok);
    `start`'tan önceki veri yalnız ısınma içindir (o tarihte oluşan emirler alınmaz)."""
    start_ts = pd.Timestamp(start, tz="UTC") if pd.Timestamp(start).tzinfo is None \
        else pd.Timestamp(start)
    end_ts = pd.Timestamp(end_excl, tz="UTC") if pd.Timestamp(end_excl).tzinfo is None \
        else pd.Timestamp(end_excl)
    ltf_c = ltf[ltf.index < end_ts]
    htf_c = htf[htf.index < end_ts]
    if len(ltf_c) == 0:
        raise ProtocolError("dönem için veri yok")
    orders = generate_orders_v2(ltf_c, htf_c, sp)
    s_idx = int(ltf_c.index.searchsorted(start_ts))
    sliced = ltf_c.iloc[s_idx:]
    shifted = [
        replace(o, created_idx=o.created_idx - s_idx, expiry_idx=o.expiry_idx - s_idx)
        for o in orders if o.created_idx >= s_idx
    ]
    res = Backtester(bp).run(sliced, shifted, liquidate_at_end=True)
    info = {
        "orders_total_incl_warmup": len(orders),
        "orders_in_period": len(shifted),
        "period_first_bar": str(sliced.index[0]) if len(sliced) else None,
        "period_last_bar": str(sliced.index[-1]) if len(sliced) else None,
        "period_bars": int(len(sliced)),
    }
    return res, info


def combine(results: dict[str, BacktestResult], initial: float) -> dict:
    """E3: birleşik PF (net, maliyet sonrası), toplam işlem, toplam equity DD."""
    trades = [t for r in results.values() for t in r.trades]
    wins = sum(t.pnl_usd for t in trades if t.pnl_usd > 0)
    losses = abs(sum(t.pnl_usd for t in trades if t.pnl_usd <= 0))
    if losses == 0:
        pf = float("inf") if wins > 0 else 0.0
    else:
        pf = wins / losses

    eq = pd.concat({k: v.equity_curve for k, v in results.items()}, axis=1).sort_index()
    eq = eq.ffill()
    for c in eq.columns:
        eq[c] = eq[c].fillna(initial)
    total = eq.sum(axis=1)
    peak = total.cummax()
    dd = float(((peak - total) / peak).max()) if len(total) else 0.0

    by_year: dict[str, dict] = {}
    for t in trades:
        y = str(pd.Timestamp(t.meta["timestamp"]).year)
        d = by_year.setdefault(y, {"trades": 0, "gp": 0.0, "gl": 0.0, "net": 0.0})
        d["trades"] += 1
        d["net"] += t.pnl_usd
        if t.pnl_usd > 0:
            d["gp"] += t.pnl_usd
        else:
            d["gl"] += abs(t.pnl_usd)
    for y, d in by_year.items():
        d["pf"] = _num(d["gp"] / d["gl"]) if d["gl"] > 0 else ("inf" if d["gp"] > 0 else 0.0)
        d["net"] = round(d["net"], 2)
        del d["gp"], d["gl"]

    return {
        "total_trades": len(trades),
        "profit_factor": pf,
        "max_drawdown": dd,
        "expectancy_r": float(np.mean([t.pnl_r for t in trades])) if trades else 0.0,
        "win_rate": (sum(1 for t in trades if t.pnl_usd > 0) / len(trades)) if trades else 0.0,
        "initial_total": initial * len(results),
        "final_total": float(total.iloc[-1]) if len(total) else None,
        "longs": sum(1 for t in trades if t.side == "long"),
        "shorts": sum(1 for t in trades if t.side == "short"),
        "forced_closes": sum(r.forced_closes for r in results.values()),
        "gap_stopouts": sum(r.gap_stopouts for r in results.values()),
        "gap_target_exits": sum(r.gap_target_exits for r in results.values()),
        "invalid_geometry_orders": sum(r.invalid_geometry_orders for r in results.values()),
        "by_year": by_year,
    }


def evaluate_insample(c: dict) -> dict:
    g = INSAMPLE_GATES
    gates = {
        f"PF > {g['min_pf']}": bool(c["profit_factor"] > g["min_pf"]),
        f"işlem >= {g['min_trades']}": bool(c["total_trades"] >= g["min_trades"]),
        f"DD < %{g['max_dd']*100:.0f}": bool(c["max_drawdown"] < g["max_dd"]),
    }
    return {"gates": gates, "passed": all(gates.values())}


def evaluate_holdout(c: dict) -> dict:
    g = HOLDOUT_GATES
    gates = {
        f"PF > {g['min_pf']}": bool(c["profit_factor"] > g["min_pf"]),
        f"DD < %{g['max_dd']*100:.0f}": bool(c["max_drawdown"] < g["max_dd"]),
    }
    return {"gates": gates, "passed": all(gates.values())}


# ----------------------------------------------------------------- veri yükleme
def _load_symbol(data_dir: Path, symbol: str) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    lp, hp = data_dir / f"{symbol}_15m.csv", data_dir / f"{symbol}_4h.csv"
    if not lp.exists() or not hp.exists():
        raise ProtocolError(f"[{symbol}] veri yok: {lp.name} / {hp.name}")
    ltf, htf = load_csv(lp), load_csv(hp)
    if ltf.index[0].year < 2015:
        raise ProtocolError(f"[{symbol}] veri tarihleri bozuk görünüyor ({ltf.index[0]})")
    meta = {
        "ltf": data_report(ltf, "15min"), "htf": data_report(htf, "4h"),
        "ltf_file_sha256": file_sha256(lp), "htf_file_sha256": file_sha256(hp),
    }
    return ltf, htf, meta


# ----------------------------------------------------------------- koşu
def run_protocol(
    phase: str,
    data_dir: Path,
    report_dir: Path,
    symbols: tuple[str, ...] = SYMBOLS,
    periods: Periods = Periods(),
    sp: StrategyParams = StrategyParams(),
    bp: BacktestParams = BacktestParams(),
    root: Path = ROOT,
) -> dict:
    if phase not in ("insample", "holdout"):
        raise ProtocolError("phase: insample | holdout")
    report_dir.mkdir(parents=True, exist_ok=True)
    ins_path, ho_path = report_dir / INSAMPLE_FILE, report_dir / HOLDOUT_FILE
    fp = code_fingerprint(root)

    prev_ins = None
    if phase == "insample":
        if ins_path.exists():
            raise ProtocolError(
                f"{INSAMPLE_FILE} zaten var: TEK ATIŞ kullanıldı. Yeniden koşmak = yeni "
                "versiyon numarası (V2.1) + yeni tek atış. Dosyayı silme.")
    else:
        if ho_path.exists():
            raise ProtocolError(f"{HOLDOUT_FILE} zaten var: hold-out TEK ATIŞ kullanıldı.")
        if not ins_path.exists():
            raise ProtocolError("Önce in-sample koşulmalı (V2_INSAMPLE.json yok).")
        prev_ins = json.loads(ins_path.read_text(encoding="utf-8"))
        if not prev_ins.get("gates_passed"):
            raise ProtocolError("V2 in-sample kapılarında KALDI: V2 REDDEDİLDİ, hold-out koşulmaz.")
        if prev_ins.get("code_fingerprint") != fp:
            raise ProtocolError(
                "Kod/spesifikasyon in-sample'dan beri DEĞİŞMİŞ (parmak izi uyuşmuyor). "
                "Kural değişikliği = yeni versiyon + yeni tek atış.")

    loaded, data_meta, results, run_infos, slice_hashes = {}, {}, {}, {}, {}
    for s in symbols:
        ltf, htf, meta = _load_symbol(data_dir, s)
        loaded[s], data_meta[s] = (ltf, htf), meta

    ins_end = pd.Timestamp(periods.insample_end_excl, tz="UTC")
    for s in symbols:
        ltf, htf = loaded[s]
        slice_hashes[s] = {
            "ltf": frame_hash(ltf[ltf.index < ins_end]),
            "htf": frame_hash(htf[htf.index < ins_end]),
        }

    if phase == "insample":
        start, end_excl = periods.insample_start, ins_end
        for s in symbols:  # veri dönem başını kapsamalı
            first = loaded[s][0].index[0]
            if first > pd.Timestamp(start, tz="UTC") + pd.Timedelta(days=1):
                raise ProtocolError(f"[{s}] veri {start} tarihini kapsamıyor (ilk bar {first})")
    else:
        for s in symbols:
            if prev_ins["slice_hashes"].get(s) != slice_hashes[s]:
                raise ProtocolError(
                    f"[{s}] in-sample veri dilimi in-sample'dan beri DEĞİŞMİŞ.")
        start = periods.holdout_start
        end_excl = min(last_full_day_end(loaded[s][0]) for s in symbols)
        if end_excl <= pd.Timestamp(start, tz="UTC"):
            raise ProtocolError("hold-out için yeterli veri yok")

    for s in symbols:
        ltf, htf = loaded[s]
        results[s], run_infos[s] = run_period(ltf, htf, start, end_excl, sp, bp)

    combined = combine(results, bp.initial_balance)
    verdict = evaluate_insample(combined) if phase == "insample" else evaluate_holdout(combined)
    per_symbol = {s: results[s].summary() for s in symbols}

    report = {
        "version": VERSION, "phase": phase,
        "run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "period": {"start": str(pd.Timestamp(start, tz="UTC")), "end_exclusive": str(end_excl)},
        "gates": verdict["gates"], "gates_passed": verdict["passed"],
        "verdict": "GEÇTİ" if verdict["passed"] else "KALDI",
        "combined": {k: _num(v) if not isinstance(v, dict) else v for k, v in combined.items()},
        "per_symbol": per_symbol,
        "run_info": run_infos,
        "data": data_meta,
        "slice_hashes": slice_hashes,
        "code_fingerprint": fp,
        "git": _git_info(),
        "env": {"python": platform.python_version(), "pandas": pd.__version__,
                "numpy": np.__version__},
        "params": {"strategy": dataclasses.asdict(sp), "backtest": dataclasses.asdict(bp)},
        "insample_reference": (
            {"verdict": prev_ins["verdict"], "run_utc": prev_ins["run_utc"]} if prev_ins else None),
    }
    report = _clean(report)
    out = ins_path if phase == "insample" else ho_path
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    out.with_suffix(".md").write_text(render_markdown(report), encoding="utf-8")
    return report


def render_markdown(r: dict) -> str:
    c = r["combined"]
    ph = "IN-SAMPLE (2020-2024)" if r["phase"] == "insample" else "HOLD-OUT (2025+)"
    L = [f"# V2 — {ph}: **{r['verdict']}**", "",
         f"Koşu: {r['run_utc']} · Dönem: {r['period']['start'][:10]} → {r['period']['end_exclusive'][:10]} (hariç)",
         "", "## Kapılar (önceden sabit)"]
    for k, ok in r["gates"].items():
        L.append(f"- {'✅' if ok else '❌'} {k}")
    L += ["", "## Birleşik sonuç (BTCUSDT + ETHUSDT, maliyetler dahil)",
          f"- Profit factor: **{c['profit_factor']}**",
          f"- İşlem sayısı: **{c['total_trades']}** (long {c['longs']} / short {c['shorts']})",
          f"- Max drawdown: **%{float(c['max_drawdown'])*100:.2f}**",
          f"- Beklenti: {float(c['expectancy_r']):.3f} R · Kazanma oranı: %{float(c['win_rate'])*100:.1f}",
          f"- Başlangıç → bitiş (toplam): {c['initial_total']:.0f} → {float(c['final_total']):.0f}",
          f"- Zorla kapanış: {c['forced_closes']} · gap-stop: {c['gap_stopouts']} · "
          f"gap-hedef: {c['gap_target_exits']} · geçersiz geometri: {c['invalid_geometry_orders']}",
          "", "## Yıl bazında (bilgi amaçlı, kapı değil)", "| Yıl | İşlem | PF | Net $ |", "|---|---:|---:|---:|"]
    for y in sorted(c["by_year"]):
        d = c["by_year"][y]
        L.append(f"| {y} | {d['trades']} | {d['pf']} | {d['net']} |")
    L += ["", "## Sembol bazında"]
    for s, sm in r["per_symbol"].items():
        L.append(f"- {s}: işlem {sm['total_trades']}, PF {sm['profit_factor']}, "
                 f"DD %{float(sm['max_drawdown'])*100:.1f}, beklenti {sm['expectancy_r']} R")
    L += ["", "## Veri sağlığı"]
    for s, d in r["data"].items():
        L.append(f"- {s}: 15m {d['ltf']['first'][:10]} → {d['ltf']['last'][:16]}, "
                 f"eksik bar {d['ltf']['missing_bars']} ({d['ltf']['gap_count']} boşluk, "
                 f"en uzunu {d['ltf']['max_gap_bars']} bar); "
                 f"4h eksik bar {d['htf']['missing_bars']} (E10: doldurulmaz, barlar ardışık kabul edilir)")
    L += ["", "## Tekrar üretilebilirlik",
          f"- Kod parmak izi: `{r['code_fingerprint'][:16]}…` · git: {r['git']['commit']} (dirty={r['git']['dirty']})",
          f"- Python {r['env']['python']}, pandas {r['env']['pandas']}", "",
          "> Kural: bu sonuç kapı kriterleriyle raporlanır, süslenmez. KALDI ise V2 REDDEDİLDİ, "
          "parametre kurcalanmaz (DEVIR_NOTU §2, §8)."]
    return "\n".join(L) + "\n"
