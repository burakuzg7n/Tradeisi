"""Oran rotasyonu — ccxt/binance-trade-bot algoritmasinin yeniden yazimi (kod kopyasi degil).

Asil botla ayni mantik:
  * Baslangicta her (A, B) cifti icin esik = fiyat_A / fiyat_B kaydedilir.
  * A tutulurken her B icin skor = (1 - islem_ucreti) x (fiyat_A/fiyat_B) / esik(A,B) - 1 - marj.
    (asil botun 'use_margin' secenegi; ciftler arasi karsilastirilabilir olan bicim budur)
  * Skoru > 0 olan en iyi B'ye gecilir.
  * B ALINDIGINDA, B'ye GIDEN tum ciftlerin esigi guncellenir: esik(X, B) = fiyat_X / fiyat_B.
    Yani B'ye bir daha ancak, B o gunku alimdan daha ucuza (X cinsinden) geldiginde donulur.
Amac, zamanla elde tutulan coin adedini artirmaktir. Yon gorusu degildir; fuzyon oylamasina katilmaz.
"""
from ..motor import Emir
from ..strateji import Strateji


class OranRotasyon(Strateji):
    ad = "oran_rotasyon"
    baslik = "Coinler arası oran rotasyonu (tek coin, sürekli pozisyonda)"
    kaynak = "ccxt/binance-trade-bot"
    oy_verir = False
    marj = 0.008       # asil botun varsayilan scout_margin degeri (%0,8)
    agirlik = 0.95

    def hazirla(self, piyasa, k_bas, ayar):
        self.esik = {}         # (a, b) -> a/b esik orani
        self.elde = None
        tek = (ayar["komisyon_bps"] + ayar["kayma_bps"]) / 10_000.0
        self.islem_ucreti = tek + tek - tek * tek     # sat + al

    def _fiyatlar(self, k, b):
        out = {}
        for s in b.piyasa.semboller:
            i = b.idx[s][k]
            if i >= 0:
                out[s] = b.c[s][i]
        return out

    def bar(self, k, hesap, b):
        f = self._fiyatlar(k, b)
        if len(f) < 2:
            return []
        for a in f:                       # henuz esigi olmayan ciftleri baslat
            for x in f:
                if a != x and (a, x) not in self.esik:
                    self.esik[(a, x)] = f[a] / f[x]
        if self.elde is None:
            self.elde = next(iter(f))
        a = self.elde
        if a not in f:
            return []
        if hesap.niyet(a) == 0:           # baslangic ya da kilit sonrasi yeniden alim
            return [Emir(a, 1, agirlik=self.agirlik, neden="rotasyon: elde tutulan coin alınıyor")]
        en_iyi, en_skor = None, 0.0
        for x, px in f.items():
            if x == a:
                continue
            skor = (1.0 - self.islem_ucreti) * (f[a] / px) / self.esik[(a, x)] - 1.0 - self.marj
            if skor > en_skor:
                en_iyi, en_skor = x, skor
        if en_iyi is None:
            return []
        self.elde = en_iyi
        for x in f:                       # en_iyi'ye GIDEN ciftlerin esigi
            if x != en_iyi:
                self.esik[(x, en_iyi)] = f[x] / f[en_iyi]
        neden = f"{a}→{en_iyi}: oran eşiğin ücret + marj sonrası %{en_skor * 100:.2f} üstünde"
        return [Emir(a, 0, neden=neden), Emir(en_iyi, 1, agirlik=self.agirlik, neden=neden)]
