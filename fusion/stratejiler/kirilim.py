"""Trend filtreli kanal kirilimi — timercrack/trader'daki 'brother2' stratejisinin yeniden yazimi
(kod kopyasi degil).

Asil stratejiyle ayni kurallar:
  * kisa/uzun yumusatilmis ortalama (onceki x (n-1) + kapanis) / n  -> trend yonu
  * KAPANISLARIN break_n barlik en yuksegi / en dusugu -> kanal (bir onceki barin degeri)
  * AL  : kisa > uzun ve kapanis >= kanal ustu     SAT: kisa < uzun ve kapanis <= kanal alti
  * Cikis (izleyen stop): long'da kapanis <= giristen beri en yuksek HIGH - stop_n x ATR(giris oncesi bar)
                          short'ta kapanis >= giristen beri en dusuk LOW + stop_n x ATR
  * Pozisyondayken ters sinyalle donus yok; yalniz izleyen stop cikarir.
Asil projede parametre degerleri veritabaninda tutulur (repoda yok); buradakiler klasik degerlerdir
ve hicbir veriye bakilarak ayarlanmamistir. Ek olarak motor, giristen stop_n x ATR uzakta bar-ici
koruyucu stop tutar (asil strateji gunluk kapanisla calistigi icin onda yoktur).
"""
from .. import gostergeler as g
from ..motor import Emir
from ..strateji import Strateji


class Kirilim(Strateji):
    ad = "kirilim"
    baslik = "Trend filtreli kapanış kanalı kırılımı + izleyen ATR stop"
    kaynak = "timercrack/trader"
    break_n, atr_n, kisa_n, uzun_n, stop_n = 20, 20, 20, 60, 3.0

    def hazirla(self, piyasa, k_bas, ayar):
        self._d = {}
        self._uc = {}        # sembol -> (k_giris, giristen beri uc deger)
        for s in piyasa.semboller:
            b = piyasa.barlar[s]
            kisa, uzun = g.wilder(b.c, self.kisa_n), g.wilder(b.c, self.uzun_n)
            ust = g.shift(g.highest(b.c, self.break_n), 1)
            alt = g.shift(g.lowest(b.c, self.break_n), 1)
            self._d[s] = {"al": ((kisa > uzun) & (b.c >= ust)).tolist(),
                          "sat": ((kisa < uzun) & (b.c <= alt)).tolist(),
                          "atr": g.atr(b.h, b.l, b.c, self.atr_n).tolist()}

    def bar(self, k, hesap, b):
        emirler = []
        for s in b.piyasa.semboller:
            i = b.idx[s][k]
            if i < 0:
                continue
            d = self._d[s]
            p = hesap.poz.get(s)
            if p is not None:
                if s in hesap.bekleyen:
                    continue
                long = p.adet > 0
                kayit = self._uc.get(s)
                if kayit is None or kayit[0] != p.k_giris:
                    # giris barinda yalniz uc deger baslatilir (asil kodda da ilk barda cikis yok)
                    self._uc[s] = (p.k_giris, b.h[s][i] if long else b.l[s][i])
                    continue
                uc = kayit[1]
                mesafe = abs(p.giris - p.stop) if p.stop is not None else self.stop_n * d["atr"][i]
                c = b.c[s][i]
                if (long and c <= uc - mesafe) or (not long and c >= uc + mesafe):
                    emirler.append(Emir(s, 0, neden="izleyen stop (kapanış)"))
                else:
                    self._uc[s] = (p.k_giris, max(uc, b.h[s][i]) if long else min(uc, b.l[s][i]))
                continue
            if hesap.niyet(s) != 0:
                continue
            atr = d["atr"][i]
            if atr != atr or atr <= 0:
                continue
            if d["al"][i]:
                emirler.append(Emir(s, 1, stop_mesafe=self.stop_n * atr,
                                    neden=f"trend yukarı, kapanış {self.break_n} barlık kanalın üstünde"))
            elif d["sat"][i] and b.ayar["short_acik"]:
                emirler.append(Emir(s, -1, stop_mesafe=self.stop_n * atr,
                                    neden=f"trend aşağı, kapanış {self.break_n} barlık kanalın altında"))
        return emirler
