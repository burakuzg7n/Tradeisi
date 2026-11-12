"""Kaplumbaga tipi kanal kirilimi (timercrack/trader'in trend-takip yaklasimindan esinli)."""
from .. import gostergeler as g
from ..strateji import DiziStrateji


class Kirilim(DiziStrateji):
    ad = "kirilim"
    baslik = "Donchian 20/10 kırılımı + 2 ATR stop"
    kaynak = "timercrack/trader"
    stop_atr = 2.0
    giris_n, cikis_n = 20, 10

    def diziler(self, sembol, bars, piyasa):
        ust = g.shift(g.highest(bars.h, self.giris_n), 1)
        alt = g.shift(g.lowest(bars.l, self.giris_n), 1)
        cik_alt = g.shift(g.lowest(bars.l, self.cikis_n), 1)
        cik_ust = g.shift(g.highest(bars.h, self.cikis_n), 1)
        return {"le": bars.c > ust, "se": bars.c < alt, "lx": bars.c < cik_alt, "sx": bars.c > cik_ust}

    def neden(self, sembol, i, yon):
        return f"{self.giris_n} barlık kanalın {'üstünde' if yon > 0 else 'altında'} kapanış"
