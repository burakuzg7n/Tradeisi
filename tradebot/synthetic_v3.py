"""V3 fizibilite için sentetik 15m veri üreteci (GERÇEK VERİ DEĞİL).

Varsayımlar sonuç görülmeden sabitlenmiştir (docs/V3_SPEC_TASLAK.md §6b):
- 5 sembol, tüm 15m mumlar mevcut.
- Günlük oynaklık σ_d (senaryo): 0,025 / 0,04 / 0,06.
- Gün içi oynaklık profili: Asya (00:00–06:45) ×0,8, tetik penceresi (07:00–19:45)
  ×1,15, akşam (20:00–23:45) ×0,9; günlük varyans σ_d² olacak şekilde normalize.
- Semboller arası korelasyon ρ (senaryo): 0,5 / 0,8 (ortak faktör modeli).
- Yenilikler: Student-t (sd = 3), birim varyansa ölçekli (kalın kuyruk).
- Rejim: günlük sürüklenme durumları {yukarı, aşağı, yatay}; trendde |μ| = 0,3 σ_d/gün;
  her gün %3 olasılıkla rejim değişir (ortalama süre ~33 gün); yeni rejim "trend
  ağırlıklı" senaryoda %35 yukarı/%35 aşağı/%30 yatay, "yatay ağırlıklı" senaryoda
  %15/%15/%70 seçilir. Rejim tüm sembollerde ortaktır.
- Mum içi high/low: max/min(open, close) × exp(±|N(0, 0,5 σ_mum)|).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .strategy_v3 import BAR_MS, DAY_MS

SLOT_MULT = np.array([0.8] * 28 + [1.15] * 52 + [0.9] * 16)
SLOT_MULT = SLOT_MULT / np.sqrt((SLOT_MULT ** 2).mean())          # günlük varyans korunur
T_DF = 3
SWITCH_P = 0.03
TREND_MU = 0.3
REGIME_WEIGHTS = {"trend": (0.35, 0.35, 0.30), "yatay": (0.15, 0.15, 0.70)}


def generate(symbols, first_day: int, n_days: int, sigma_d: float, rho: float,
             regime: str, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    w = REGIME_WEIGHTS[regime]
    states = np.empty(n_days, dtype=int)                 # 0 yukarı, 1 aşağı, 2 yatay
    states[0] = rng.choice(3, p=w)
    for d in range(1, n_days):
        states[d] = rng.choice(3, p=w) if rng.random() < SWITCH_P else states[d - 1]
    mu_day = np.where(states == 0, TREND_MU, np.where(states == 1, -TREND_MU, 0.0)) * sigma_d
    nb = n_days * 96
    sig_bar = sigma_d / np.sqrt(96) * np.tile(SLOT_MULT, n_days)
    mu_bar = np.repeat(mu_day / 96, 96)
    tscale = np.sqrt((T_DF - 2) / T_DF)
    common = rng.standard_t(T_DF, nb) * tscale
    out = {}
    idx = pd.Index([(first_day + k // 96) * DAY_MS + (k % 96) * BAR_MS for k in range(nb)])
    for s in symbols:
        own = rng.standard_t(T_DF, nb) * tscale
        z = np.sqrt(rho) * common + np.sqrt(1 - rho) * own
        r = mu_bar + sig_bar * z
        c = 100 * np.exp(np.cumsum(r))
        o = np.r_[100.0, c[:-1]]
        h = np.maximum(o, c) * np.exp(np.abs(rng.normal(0, 0.5, nb)) * sig_bar)
        lo = np.minimum(o, c) * np.exp(-np.abs(rng.normal(0, 0.5, nb)) * sig_bar)
        out[s] = pd.DataFrame(dict(open=o, high=h, low=lo, close=c), index=idx)
    return out
