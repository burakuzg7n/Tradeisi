"""Ajan kurulu (TauricResearch/TradingAgents'in rol dagilimindan esinli; LLM'siz, kural tabanli).

Analistler  : trend, momentum, hacim, piyasa (BTC rejimi) -> her biri -1..+1 puan
Arastirmacilar: boga tezi (arti puanlar) ve ayi tezi (eksi puanlar)
Trader      : agirlikli net puana gore AL / SAT / BEKLE
Risk yoneticisi: oynaklik asiriysa veto eder, yuksekse pozisyonu kucultur
"""
import numpy as np

from .. import gostergeler as g
from ..strateji import DiziStrateji

AGIRLIK = {"trend": 0.35, "momentum": 0.25, "hacim": 0.15, "piyasa": 0.25}


class AjanKurulu(DiziStrateji):
    ad = "ajan_kurulu"
    baslik = "Analist kurulu: trend + momentum + hacim + BTC rejimi, risk yöneticisi vetolu"
    kaynak = "TauricResearch/TradingAgents"
    stop_atr = 2.0
    kar_atr = 3.0
    giris_esik, cikis_esik = 0.40, 0.05

    def hazirla(self, piyasa, k_bas, ayar):
        self._p = {}
        ref = "BTCUSDT" if "BTCUSDT" in piyasa.barlar else piyasa.semboller[0]
        rb = piyasa.barlar[ref]
        with np.errstate(invalid="ignore"):
            self._rejim = np.where(g.ema(rb.c, 50) > g.ema(rb.c, 200), 0.6, -0.6)
        self._rejim[np.isnan(g.ema(rb.c, 200))] = np.nan
        self._ref = ref
        super().hazirla(piyasa, k_bas, ayar)

    def diziler(self, sembol, bars, piyasa):
        c = bars.c
        atr = piyasa.atr[sembol]
        with np.errstate(divide="ignore", invalid="ignore"):
            trend = 0.5 * np.clip((g.ema(c, 20) - g.ema(c, 50)) / atr, -1, 1) \
                + 0.5 * np.sign(c - g.ema(c, 200))
            momentum = np.clip((g.rsi(c, 14) - 50.0) / 25.0, -1, 1)
            hacim = np.clip(g.zscore(bars.v, 96) / 2.0, 0, 1) * np.sign(c - bars.o)
            piyasa_p = piyasa.hizala(self._ref, sembol, self._rejim)
            oyn_oran = piyasa.oyn_orani(sembol)
        net = (AGIRLIK["trend"] * trend + AGIRLIK["momentum"] * momentum
               + AGIRLIK["hacim"] * hacim + AGIRLIK["piyasa"] * piyasa_p)
        with np.errstate(invalid="ignore"):
            risk_ok = oyn_oran < 2.5
            carpan = np.clip(1.0 / oyn_oran, 0.5, 1.0)
            d = {"le": (net > self.giris_esik) & risk_ok, "lx": net < self.cikis_esik,
                 "se": (net < -self.giris_esik) & risk_ok, "sx": net > -self.cikis_esik,
                 "carpan": carpan}
        self._p[sembol] = {"trend": trend, "momentum": momentum, "hacim": hacim,
                           "piyasa": piyasa_p, "net": net, "oyn": oyn_oran, "carpan": carpan}
        return d

    def puanlar(self, sembol, i):
        """Panel icin: o bardaki kurul puanlari (nan -> None)."""
        p = self._p.get(sembol)
        if p is None or i < 0:
            return None
        return {k: (None if v[i] != v[i] else round(float(v[i]), 3)) for k, v in p.items()}

    def neden(self, sembol, i, yon):
        p = self._p[sembol]
        ad = {"trend": "trend", "momentum": "momentum", "hacim": "hacim", "piyasa": "BTC rejimi"}
        boga = [f"{ad[k]} {p[k][i]:+.2f}" for k in AGIRLIK if p[k][i] > 0.05]
        ayi = [f"{ad[k]} {p[k][i]:+.2f}" for k in AGIRLIK if p[k][i] < -0.05]
        return (f"Boğa tezi: {', '.join(boga) or 'yok'} | Ayı tezi: {', '.join(ayi) or 'yok'} | "
                f"Trader: net {p['net'][i]:+.2f} → {'AL' if yon > 0 else 'SAT'} | "
                f"Risk yöneticisi: oynaklık ×{p['oyn'][i]:.1f}, boyut ×{p['carpan'][i]:.2f}")
