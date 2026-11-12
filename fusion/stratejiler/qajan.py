"""Q-ogrenme ajani (TradeMaster'in 'veri -> ortam -> ajan -> degerlendirme' hattindan esinli).

Tablo tabanli pekistirmeli ogrenme. Ajan YALNIZ degerlendirme baslangicindan ONCEKI
barlarla egitilir (k_bas oncesi); degerlendirme doneminde ogrenmez. Tohum sabit: ayni
veri ayni politikayi uretir.
Durum : trend(3) x RSI(3) x 1 gunluk yon(2) x oynaklik(2) x mevcut pozisyon(3)
Eylem : 0 nakit, 1 long, 2 short
Odul  : pozisyon x sonraki bar getirisi - pozisyon degisim maliyeti
"""
import random

import numpy as np

from .. import gostergeler as g
from ..motor import Emir
from ..strateji import Strateji

YON = (0, 1, -1)


class QAjan(Strateji):
    ad = "q_ajan"
    baslik = "Pekiştirmeli öğrenme ajanı (Q-öğrenme, yalnız geçmişle eğitilir)"
    kaynak = "TradeMaster-NTU/TradeMaster"
    stop_atr = 3.0
    egitim_bar, tur, alfa, gama, kesif = 20_000, 4, 0.05, 0.98, 0.15
    min_egitim = 500

    def _durumlar(self, bars, atr, oyn_oran):
        c = bars.c
        with np.errstate(divide="ignore", invalid="ignore"):
            t = (g.ema(c, 20) - g.ema(c, 50)) / atr
            rsi = g.rsi(c, 14)
            yon = g.roc(c, 96)
            d = (np.where(t > 0.5, 2, np.where(t < -0.5, 0, 1)) * 12
                 + np.where(rsi > 60, 2, np.where(rsi < 40, 0, 1)) * 4
                 + np.where(yon > 0, 1, 0) * 2 + np.where(oyn_oran > 1.0, 1, 0))
        gecersiz = np.isnan(t) | np.isnan(rsi) | np.isnan(yon) | np.isnan(oyn_oran)
        d = d.astype(int)
        d[gecersiz] = -1
        return d

    _anahtar = None      # egitimin yapildigi veri dilimi; ayni dilimde yeniden egitilmez
    egitildi = 0

    def sifirla(self):
        self._anahtar = None

    def hazirla(self, piyasa, k_bas, ayar):
        self._durum = {}
        maliyet = 2 * (ayar["komisyon_bps"] + ayar["kayma_bps"]) / 10_000.0
        yonler = (0, 1) if not ayar["short_acik"] else (0, 1, 2)
        self._yonler = yonler
        t_bas = int(piyasa.T[k_bas]) if k_bas < len(piyasa.T) else int(piyasa.T[-1]) + 1
        dilimler = {}
        for s in piyasa.semboller:
            bars = piyasa.barlar[s]
            d = self._durumlar(bars, piyasa.atr[s], piyasa.oyn_orani(s))
            self._durum[s] = d.tolist()
            son = int(np.searchsorted(bars.ts, t_bas))      # egitim: yalniz t_bas oncesi
            bas = max(0, son - self.egitim_bar)
            dilimler[s] = (d, bars, bas, son)
        anahtar = (t_bas, maliyet, yonler,
                   tuple((s, int(v[1].ts[v[2]]) if v[3] > v[2] else 0, v[3] - v[2])
                         for s, v in dilimler.items()))
        if anahtar == self._anahtar:
            return                                          # canli modda her mumda yeniden egitme
        self._anahtar = anahtar
        self.q = [[0.0, 0.0, 0.0] for _ in range(36 * 3)]
        self.egitildi = 0
        rnd = random.Random(1234)
        q, alfa, gama = self.q, self.alfa, self.gama
        for s, (d, bars, bas, son) in dilimler.items():
            dl, cl = d[bas:son].tolist(), bars.c[bas:son].tolist()
            if len(dl) < self.min_egitim:
                continue
            self.egitildi += len(dl)
            for _ in range(self.tur):
                poz = 0
                for i in range(len(dl) - 1):
                    if dl[i] < 0 or dl[i + 1] < 0:
                        poz = 0
                        continue
                    durum = dl[i] * 3 + poz
                    satir = q[durum]
                    if rnd.random() < self.kesif:
                        eylem = rnd.choice(yonler)
                    else:
                        eylem = max(yonler, key=satir.__getitem__)
                    odul = YON[eylem] * (cl[i + 1] / cl[i] - 1.0)
                    if eylem != poz:
                        odul -= maliyet * (1.0 if 0 in (eylem, poz) else 2.0) / 2.0
                    sonraki = q[dl[i + 1] * 3 + eylem]
                    satir[eylem] += alfa * (odul + gama * max(sonraki[y] for y in yonler) - satir[eylem])
                    poz = eylem

    def bar(self, k, hesap, b):
        if not self.egitildi:
            return []
        emirler = []
        for s in b.piyasa.semboller:
            i = b.idx[s][k]
            if i < 0 or self._durum[s][i] < 0:
                continue
            atr = b.atr[s][i]
            if atr != atr or atr <= 0:
                continue
            n = hesap.niyet(s)
            poz = 0 if n == 0 else (1 if n > 0 else 2)
            satir = self.q[self._durum[s][i] * 3 + poz]
            eylem = max(self._yonler, key=satir.__getitem__)
            if satir[eylem] <= satir[poz] or eylem == poz:
                continue                                  # esitlikte mevcut durumu koru
            if eylem == 0:
                emirler.append(Emir(s, 0, neden="Q-ajan: nakde geç"))
            else:
                emirler.append(Emir(s, YON[eylem], stop_mesafe=self.stop_atr * atr,
                                    neden=f"Q-ajan: durum {self._durum[s][i]} için en yüksek değerli eylem"))
        return emirler
