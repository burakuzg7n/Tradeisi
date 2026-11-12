"""Ortalamaya donus (freqtrade toplulugundaki klasik RSI + Bollinger kaliplarindan esinli)."""
from .. import gostergeler as g
from ..strateji import DiziStrateji


class OrtalamayaDonus(DiziStrateji):
    ad = "ortalamaya_donus"
    baslik = "RSI + Bollinger dönüşü, EMA 200 yönünde"
    kaynak = "freqtrade"
    stop_atr = 2.5

    def diziler(self, sembol, bars, piyasa):
        c = bars.c
        orta, sapma = g.sma(c, 20), g.std(c, 20)
        rsi, e200 = g.rsi(c, 14), g.ema(c, 200)
        self._rsi = getattr(self, "_rsi", {})
        self._rsi[sembol] = rsi
        return {"le": (rsi < 30) & (c < orta - 2 * sapma) & (c > e200),
                "lx": (rsi > 55) | (c > orta),
                "se": (rsi > 70) & (c > orta + 2 * sapma) & (c < e200),
                "sx": (rsi < 45) | (c < orta)}

    def neden(self, sembol, i, yon):
        return f"RSI {self._rsi[sembol][i]:.0f}, fiyat Bollinger {'alt' if yon > 0 else 'üst'} bandının dışında"
