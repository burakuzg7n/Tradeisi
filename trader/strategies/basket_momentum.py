"""SEPET MOMENTUM — capraz kesit momentum (piyasa-notr sepet).

Yeni bir strateji AILESIDIR: onceki dort reddedilen stratejinin (V1 sweep+FVG,
V2 sweep+CHoCH, Plan B donem sonu kiris, V3 seans kirilimi) hicbiri tek
varlikli, yonelimli ve zaman-serisi momentum degildir. Burada *goreceli*
gucluluk-zayiflik siralamasi kullanilir ve net pozisyon ~0 tutulur.

EKONOMIK GEREKCE (bastan sona veriye bakmadan yazildi):
  * Farkli varliklar arasinda fiyat farklari kisa vadede tam kapanmaz; yavas
    bilgi yayilimi (anchoring / underreaction) orta vadede momentum yaratir.
  * Kazanan tarafi long, kaybedeni short almak piyasa yonu riskini (beta)
    alir; getiri kaynagi *goreceli* siralamadir.
  * Bagimsiz kanit: Jegadeesh & Titman (1993) capraz kesit momentum (hisse),
    Asness/Moskowitz/Pedersen (2013) "Value and Momentum Everywhere"
    (vadeli islemler dahil birçok varlik sinifinda), Moskowitz/Ooi/Pedersen
    (2012) zaman-serisi momentum. Kripto vadeli islemleri bunlara en yakin
    siniftir: 7/24 islem, yeni yatirimci akisi, kazanc belirtilmeyen.

KURALLAR (bu dosya veriye bakmadan sabitlendi; parametreler buradan
optimize EDILMEZ):
  EVREN
    - Aday havuz: daha once indirilmis USDT perpetual semboller.
    - Nokta-in-zaman evren: her rebalance tarihinde son 30 gunluk hacim
      (volume x close) ile ilk N sembol. Hacim *o tarihte* olcumlenir.
    - N = 10, long bacak 3, short bacak 3.
    - BILINEN SINIR: havuz bugun hâlâ islemde olan coinlerden kurulur; delist
      olmus coinler kapsam disidir -> HAYATTA KALMA YANLILIGI vardir ve
      sonucu IYIMSER yonde etkiler. Rapor bunu acikca yazar.
  MOMENTUM
    - L = 30 gun, skip = 7 gun (son hafta haric): mom = close[t-7]/close[t-37] - 1
    - skip, kisa vadeli tersine donus (1 haftalik reversal) etkisini azaltir.
  REBALANCE
    - Her 7 gunde bir (Pazartesi 00:00 UTC).
  AGIRLIKLAR
    - Long bacak: en yuksek 3 momentum. Short bacak: en dusuk 3 momentum.
    - Risk esitligi: w_i ∝ 1/vol_i, vol_i = son 60 gunluk gunluk log getiri
      std (yilliklandirilmis). Bacak ici normalize edilir (toplam 1).
    - Toplam brut pozisyon G = 2.0 (equity'nin 2 kati); long bacak +G/2,
      short bacak -G/2 -> net ~0.
  CIKIS
    - Pozisyon bazli stop YOK. Pozisyonlar haftalik rebalance ile doner;
      evrenden dusana agirlik 0 (kapat).
    - Risk sinirlari motorun kendi kill switch'i ile uygulanir.

HEDEF FIYAT ARASI: 1R = islem basina equity * %0.5 (stop yoksa notional uzerinden).
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from ..strategy import Panel, Signal

STRATEGY_NAME = "sepet_momentum"


class BasketMomentum:
    """Capraz kesit momentum sepeti (piyasa-notr)."""

    name = STRATEGY_NAME
    research_candidate = True      # protokol kapilarina tabi
    timeframe = "1d"

    def __init__(
        self,
        universe_size: int = 10,
        long_leg: int = 3,
        short_leg: int = 3,
        lookback_days: int = 30,
        skip_days: int = 7,
        vol_window_days: int = 60,
        gross_leverage: float = 2.0,
        volume_window_days: int = 30,
        rebalance_weekday: int = 0,      # 0 = Pazartesi
    ):
        self.universe_size = universe_size
        self.long_leg = long_leg
        self.short_leg = short_leg
        self.lookback_days = lookback_days
        self.skip_days = skip_days
        self.vol_window_days = vol_window_days
        self.gross_leverage = gross_leverage
        self.volume_window_days = volume_window_days
        self.rebalance_weekday = rebalance_weekday
        self.last_rebalance: pd.Timestamp | None = None

    # ------------------------------------------------------------------

    def generate(self, panel: Panel, ts: pd.Timestamp) -> list[Signal]:
        # rebalance gunu degilse sinyal yok
        if ts.weekday() != self.rebalance_weekday:
            return []
        # ayni gun iki kez sinyal uretilmesin
        if self.last_rebalance is not None and ts == self.last_rebalance:
            return []
        self.last_rebalance = ts

        stats = {}
        for sym in panel.symbols():
            df = panel.until(sym, ts)
            if len(df) < self.lookback_days + self.skip_days + 2:
                continue
            close = df["close"]
            base = close.shift(self.skip_days)
            if len(base.dropna()) < 2:
                continue
            mom = float(base.iloc[-1] / base.iloc[-1 - self.lookback_days] - 1.0)
            rets = np.log(close / close.shift(1)).dropna()
            vol_window = rets.tail(self.vol_window_days)
            if len(vol_window) < max(10, self.vol_window_days // 2):
                continue
            vol = float(vol_window.std(ddof=1) * np.sqrt(365))
            if not np.isfinite(vol) or vol <= 0:
                continue
            quote_vol_window = (df["volume"] * df["close"]).tail(self.volume_window_days)
            if len(quote_vol_window) < 5:
                continue
            qv = float(quote_vol_window.mean())
            if not np.isfinite(qv) or qv <= 0:
                continue
            stats[sym] = {"momentum": mom, "vol": vol, "quote_vol": qv}

        if len(stats) < self.long_leg + self.short_leg:
            return []

        # 1) nokta-in-zaman evren: hacim
        by_volume = sorted(stats.items(), key=lambda kv: kv[1]["quote_vol"], reverse=True)
        universe = [s for s, _ in by_volume[: self.universe_size]]

        # 2) momentum siralamasi (evren icinde)
        ranked = sorted(universe, key=lambda s: stats[s]["momentum"], reverse=True)
        longs = ranked[: self.long_leg]
        shorts = ranked[-self.short_leg:]

        signals: list[Signal] = []
        leg_notional = self.gross_leverage / 2.0

        long_w = self._inverse_vol_weights(longs, stats)
        short_w = self._inverse_vol_weights(shorts, stats)

        for sym in universe:
            if sym in long_w:
                weight = long_w[sym] * leg_notional
                side = "long"
            elif sym in short_w:
                weight = -short_w[sym] * leg_notional
                side = "short"
            else:
                weight = 0.0
                side = "flat"
            signals.append(Signal(
                symbol=sym,
                side=side,
                action="target_weight",
                weight=weight,
                ts=ts.isoformat(),
                meta={
                    "strategy": self.name,
                    "momentum": round(stats[sym]["momentum"], 6),
                    "vol": round(stats[sym]["vol"], 6),
                    "quote_vol": round(stats[sym]["quote_vol"], 2),
                    "in_universe": True,
                    "leg": "long" if side == "long" else ("short" if side == "short" else "flat"),
                },
            ))

        # Evrenden dusmus semboller: agirlik 0 (pozisyon kapat)
        for sym, st in stats.items():
            if sym in universe:
                continue
            signals.append(Signal(
                symbol=sym,
                side="flat",
                action="target_weight",
                weight=0.0,
                ts=ts.isoformat(),
                meta={"strategy": self.name, "momentum": round(st["momentum"], 6),
                      "in_universe": False, "leg": "flat"},
            ))
        return signals

    @staticmethod
    def _inverse_vol_weights(symbols: list[str], stats: dict) -> dict[str, float]:
        # `math.fsum`: toplama sirasi degisse de sonuc degismesin
        # (float toplamasi siraya baglidir; determinizm icin onemli).
        inv = {s: 1.0 / max(stats[s]["vol"], 1e-9) for s in symbols}
        total = math.fsum(inv.values())
        if total <= 0:
            n = len(symbols)
            return {s: 1.0 / n for s in symbols}
        return {s: v / total for s, v in inv.items()}
