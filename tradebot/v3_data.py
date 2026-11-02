"""V3 veri: Binance USDⓈ-M PERPETUAL 15m mumları + sağlık raporu (docs/V3_SPEC_TASLAK.md §2, §4.9).

YALNIZ veri indirir ve denetler; strateji/performans hesabı yapmaz.
- Kaynak fapi.binance.com, contractType=PERPETUAL, son işlem fiyatı OHLC, interval=15m.
- Yalnız KAPANMIŞ mumlar (açılış + 15 dk ≤ şimdi).
- Listeleme = min(onboardDate'in 15m'ye yuvarlanmışı, ilk mum); öncesi eksik sayılmaz;
  dosya listelemeden sonra başlıyorsa aradaki mumlar eksik sayılır.
- Engeller: dönem içi eksik mum > %1 (in-sample ve hold-out ayrı), bozuk mum, in-sample'da
  2024-12-31 23:45 mumu yok, listeleme bilgisi yok.
- d_son (hold-out bitişi): her sembolün son tam UTC gününden büyük olmayan ve beş sembolde
  de 23:45 mumu bulunan en geç gün (yalnız mum varlığına bakılır).
"""
from __future__ import annotations

import time
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import daily_data as dd
from .strategy_v3 import BAR_MS, DAY_MS, LAST_SLOT

SYMBOLS = ("XRPUSDT", "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT")
INSAMPLE_START = date(2021, 1, 1)
INSAMPLE_END = date(2024, 12, 31)
HOLDOUT_START = date(2025, 1, 1)
DOWNLOAD_FROM = date(2019, 1, 1)
MAX_MISSING_RATIO = 0.01
KLINES_LIMIT = 1500
COLUMNS = dd.COLUMNS
PRICE_COLS = dd.PRICE_COLS


def day_index(d: date) -> int:
    return (d - date(1970, 1, 1)).days


def download_15m_rows(symbol: str, session, now_ms: int, start_ms: int,
                      pause: float = 0.2, sleep=time.sleep) -> list:
    rows: list = []
    cursor = int(start_ms)
    while True:
        batch = dd._get(session, dd.KLINES_PATH, {
            "symbol": symbol, "interval": "15m", "startTime": cursor, "limit": KLINES_LIMIT})
        if not batch:
            break
        rows.extend(batch)
        nxt = int(batch[-1][0]) + BAR_MS
        if nxt <= cursor:
            raise dd.DataError(f"{symbol}: sayfalama ilerlemiyor")
        cursor = nxt
        if len(batch) < KLINES_LIMIT or cursor + BAR_MS > now_ms:
            break
        sleep(pause)
    return [r for r in rows if int(r[0]) + BAR_MS <= now_ms]


def load_15m(path: Path) -> pd.DataFrame:
    """Motor/strateji girdisi: int ms index, open/high/low/close. Tekrar/hizasızlıkta hata."""
    raw = pd.read_csv(path)
    ts = raw["timestamp"].astype("int64")
    if (ts % BAR_MS != 0).any():
        raise ValueError(f"{Path(path).name}: 15 dakikaya hizalı olmayan mum")
    df = raw[["open", "high", "low", "close"]].astype(float)
    df.index = pd.Index(ts.to_numpy(), name="ts")
    if not df.index.is_monotonic_increasing or df.index.has_duplicates:
        raise ValueError(f"{Path(path).name}: zaman indeksi sıralı/tekil değil")
    return df


def bad_bars(df: pd.DataFrame) -> list:
    out = []
    ts = df["timestamp"]
    for t in sorted(set(ts[ts.duplicated(keep=False)].tolist())):
        out.append(f"tekrarlanan zaman damgası: {dd._iso(t)}")
    p = df[PRICE_COLS]
    nonfinite = pd.Series(~np.isfinite(p.to_numpy(dtype=float)).all(axis=1), index=df.index)
    checks = [
        (nonfinite, "sonlu olmayan fiyat (NaN/inf)"),
        ((p <= 0).any(axis=1), "sıfır/negatif fiyat"),
        (df["high"] < df["low"], "high < low"),
        ((df["open"] < df["low"]) | (df["open"] > df["high"]), "open [low, high] dışında"),
        ((df["close"] < df["low"]) | (df["close"] > df["high"]), "close [low, high] dışında"),
    ]
    for mask, label in checks:
        for t in ts[mask.fillna(False)].tolist():
            out.append(f"{label}: {dd._iso(t)}")
    return out


def _bars_in(present: set, first_bar: int, start_ms: int, end_ms_excl: int) -> dict:
    s = max(start_ms, first_bar)
    if s >= end_ms_excl:
        return {"expected_bars": 0, "missing_bars": 0, "missing_ratio": 0.0}
    expected = (end_ms_excl - s) // BAR_MS
    have = sum(1 for t in range(s, end_ms_excl, BAR_MS) if t in present)
    miss = expected - have
    return {"expected_bars": int(expected), "missing_bars": int(miss),
            "missing_ratio": miss / expected if expected else 0.0}


def build_report(frames: dict, contracts: dict, file_hashes: dict | None = None,
                 insample=(INSAMPLE_START, INSAMPLE_END), holdout_start=HOLDOUT_START) -> dict:
    file_hashes = file_hashes or {}
    ins_s, ins_e = day_index(insample[0]) * DAY_MS, (day_index(insample[1]) + 1) * DAY_MS
    blockers, per = [], {}
    for sym, df in frames.items():
        ts = df["timestamp"].astype("int64")
        warnings = []
        if not ts.is_monotonic_increasing:
            warnings.append("zaman damgaları sıralı değil")
        mis = ts[ts % BAR_MS != 0]
        if len(mis):
            warnings.append(f"15 dakikaya hizalı olmayan {len(mis)} mum")
        present = set(ts.tolist())
        first_bar, last_bar = int(ts.min()), int(ts.max())
        onboard = (contracts.get(sym) or {}).get("onboardDate")
        listed = None if onboard is None else min((int(onboard) // BAR_MS) * BAR_MS, first_bar)
        first = listed if listed is not None else first_bar
        last_full_day = last_bar // DAY_MS if (last_bar % DAY_MS) // BAR_MS == LAST_SLOT \
            else last_bar // DAY_MS - 1
        bb = bad_bars(df)
        if listed is None:
            blockers.append(f"{sym}: listeleme bilgisi (onboardDate) yok, kapsam doğrulanamaz")
        if bb:
            blockers.append(f"{sym}: {len(bb)} bozuk mum")
        ins = _bars_in(present, first, ins_s, ins_e)
        if ins["missing_ratio"] > MAX_MISSING_RATIO:
            blockers.append(f"{sym}: in-sample eksik mum oranı %{ins['missing_ratio']*100:.2f} > %1")
        end_bar = (day_index(insample[1]) * DAY_MS) + LAST_SLOT * BAR_MS
        has_end = end_bar in present
        if first <= end_bar and not has_end:
            blockers.append(f"{sym}: {insample[1]} 23:45 mumu yok")
        per[sym] = {"present": present, "first": first, "last_full_day": last_full_day,
                    "info": {"contract": contracts.get(sym), "file_sha256": file_hashes.get(sym),
                             "rows": int(len(df)), "listing": dd._iso(first),
                             "first_bar": dd._iso(first_bar), "last_bar": dd._iso(last_bar),
                             "onboard": dd._iso(onboard) if onboard is not None else None,
                             "missing_before_first_bar": int((first_bar - first) // BAR_MS),
                             "insample": ins, "insample_end_bar_present": has_end,
                             "bad_bars": bb[:50], "bad_bar_count": len(bb), "warnings": warnings}}
    # d_son: ≤ her sembolün son tam günü ve hepsinde 23:45 mumu olan en geç gün
    cap = min(v["last_full_day"] for v in per.values())
    hs = day_index(holdout_start)
    d_son = None
    for d in range(cap, hs - 1, -1):
        if all((d * DAY_MS + LAST_SLOT * BAR_MS) in v["present"] for v in per.values()):
            d_son = d
            break
    if d_son is None:
        blockers.append("hold-out için d_son bulunamadı")
    else:
        for sym, v in per.items():
            ho = _bars_in(v["present"], v["first"], hs * DAY_MS, (d_son + 1) * DAY_MS)
            v["info"]["holdout"] = ho
            if ho["missing_ratio"] > MAX_MISSING_RATIO:
                blockers.append(f"{sym}: hold-out eksik mum oranı %{ho['missing_ratio']*100:.2f} > %1")
    return {
        "kind": "V3_DATA_HEALTH",
        "note": "Yalnız veri sağlığı. Strateji/performans hesabı içermez.",
        "source": "Binance USDⓈ-M Futures, PERPETUAL, 15m, son işlem fiyatı OHLC",
        "insample": [str(insample[0]), str(insample[1])],
        "holdout": [str(holdout_start), str(dd.day_date(d_son)) if d_son is not None else None],
        "d_son": str(dd.day_date(d_son)) if d_son is not None else None,
        "max_missing_ratio": MAX_MISSING_RATIO,
        "symbols": {s: v["info"] for s, v in per.items()},
        "blockers": blockers,
        "verdict": "VERİ UYGUN" if not blockers else "VERİ ENGELLİ",
    }


def render_markdown(rep: dict) -> str:
    L = [f"# V3 veri sağlık raporu — {rep['verdict']}", "", f"_{rep['note']}_", "",
         f"- Kaynak: {rep['source']}",
         f"- In-sample: {rep['insample'][0]} → {rep['insample'][1]}",
         f"- Hold-out: {rep['holdout'][0]} → {rep['holdout'][1]} (d_son, spec §4.9)",
         f"- Eksik mum engel eşiği: > %{rep['max_missing_ratio']*100:.0f}", "", "## Engeller", ""]
    L += [f"- {b}" for b in rep["blockers"]] or ["- Yok"]
    L += ["", "## Semboller", "",
          "| Sembol | Listeleme | Son mum | In-sample eksik | 2024-12-31 23:45 | Hold-out eksik | Bozuk |",
          "|---|---|---|---|---|---|---|"]
    for s, v in rep["symbols"].items():
        ins = v["insample"]
        ho = v.get("holdout") or {"missing_bars": "-", "expected_bars": "-", "missing_ratio": 0}
        L.append(f"| {s} | {v['listing']} | {v['last_bar']} | {ins['missing_bars']}/{ins['expected_bars']} "
                 f"(%{ins['missing_ratio']*100:.3f}) | {'var' if v['insample_end_bar_present'] else 'YOK'} | "
                 f"{ho['missing_bars']}/{ho['expected_bars']} (%{float(ho['missing_ratio'])*100:.3f}) | "
                 f"{v['bad_bar_count']} |")
    L += ["", "## Ayrıntılar", ""]
    for s, v in rep["symbols"].items():
        c = v.get("contract") or {}
        L += [f"### {s}", f"- Sözleşme: {c.get('contractType')} · onboard: {v['onboard']} · durum: {c.get('status')}",
              f"- sha256: `{v['file_sha256']}` · satır: {v['rows']} · ilk mum: {v['first_bar']} · "
              f"listeleme öncesi kesik: {v['missing_before_first_bar']} mum"]
        L += [f"- Uyarı: {w}" for w in v["warnings"]]
        L += [f"- Bozuk: {b}" for b in v["bad_bars"][:10]]
        L.append("")
    return "\n".join(L)
