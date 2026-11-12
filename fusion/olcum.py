"""Degerlendirme metrikleri (TradeMaster'in cok boyutlu degerlendirme fikrinden esinli).
Yalniz olcer; 'iyi/kotu' hukmu vermez."""
from __future__ import annotations

import math

import numpy as np

YIL_MS = 365.25 * 86_400_000


def ozet(egri: list, islemler: list, adim_ms: int, sermaye: float) -> dict:
    e = np.asarray(egri, dtype=float)
    out = {"ozsermaye": float(e[-1]) if len(e) else sermaye, "getiri": 0.0, "max_dusus": 0.0,
           "sharpe": 0.0, "sortino": 0.0, "calmar": 0.0, "oynaklik": 0.0, "islem": len(islemler),
           "kazanma": 0.0, "pf": 0.0, "ort_pnl": 0.0, "ort_r": None, "ort_bar": 0.0}
    if len(e) >= 2:
        tam = np.concatenate([[sermaye], e])
        out["getiri"] = float(e[-1] / sermaye - 1.0)
        tepe = np.maximum.accumulate(tam)
        out["max_dusus"] = float(np.max(1.0 - tam / tepe))
        r = np.diff(tam) / tam[:-1]
        yil_bar = YIL_MS / adim_ms
        sd = float(np.std(r))
        if sd > 0:
            out["sharpe"] = float(np.mean(r) / sd * math.sqrt(yil_bar))
            out["oynaklik"] = float(sd * math.sqrt(yil_bar))
        asagi = r[r < 0]
        if len(asagi) > 1 and float(np.std(asagi)) > 0:
            out["sortino"] = float(np.mean(r) / float(np.std(asagi)) * math.sqrt(yil_bar))
        yil = len(r) / yil_bar
        if yil > 0 and out["max_dusus"] > 0 and e[-1] > 0:
            yillik = (e[-1] / sermaye) ** (1.0 / yil) - 1.0
            out["calmar"] = float(yillik / out["max_dusus"])
    if islemler:
        pnl = np.array([t["pnl"] for t in islemler], dtype=float)
        kazanc, kayip = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
        out["kazanma"] = float((pnl > 0).mean())
        out["pf"] = float(kazanc / kayip) if kayip > 0 else (float("inf") if kazanc > 0 else 0.0)
        out["ort_pnl"] = float(pnl.mean())
        rr = [t["r"] for t in islemler if t["r"] is not None]
        out["ort_r"] = float(np.mean(rr)) if rr else None
        out["ort_bar"] = float(np.mean([t["bar"] for t in islemler]))
    return out
