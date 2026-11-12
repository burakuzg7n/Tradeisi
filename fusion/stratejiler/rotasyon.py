"""Oran rotasyonu (ccxt/binance-trade-bot'un 'coinler arasi oran atlamasi' fikrinden esinli).

Her an tek coin tutar. Elindeki A coini, B'ye karsi son referans orana gore
komisyon + marj kadar degerlendiyse A'yi satip B'ye gecer; amac zamanla coin adedini artirmaktir.
"""
from ..motor import Emir
from ..strateji import Strateji


class OranRotasyon(Strateji):
    ad = "oran_rotasyon"
    baslik = "Coinler arası oran rotasyonu (tek coin, sürekli pozisyonda)"
    kaynak = "ccxt/binance-trade-bot"
    marj = 0.008       # atlama icin komisyon ustu gereken ek kazanc
    agirlik = 0.95

    def hazirla(self, piyasa, k_bas, ayar):
        self.ref = {}          # (a, b) -> a/b referans orani
        self.elde = None
        self.esik = 1.0 + self.marj + 4 * (ayar["komisyon_bps"] + ayar["kayma_bps"]) / 10_000.0

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
        if self.elde is None or (hesap.niyet(self.elde) == 0 and self.elde in f):
            # baslangic (ya da kilit/kapanis sonrasi yeniden giris): ilk uygun sembol
            self.elde = self.elde if self.elde in f else next(iter(f))
            for x in f:
                if x != self.elde:
                    self.ref[(self.elde, x)] = f[self.elde] / f[x]
            return [Emir(self.elde, 1, agirlik=self.agirlik, neden="rotasyon başlangıcı")]
        a = self.elde
        if a not in f:
            return []
        en_iyi, en_kazanc = None, self.esik
        for x, px in f.items():
            if x == a:
                continue
            oran = f[a] / px
            ref = self.ref.setdefault((a, x), oran)
            if oran / ref > en_kazanc:
                en_iyi, en_kazanc = x, oran / ref
        if en_iyi is None:
            return []
        self.elde = en_iyi
        for x in f:
            if x != en_iyi:
                self.ref[(en_iyi, x)] = f[en_iyi] / f[x]
        neden = f"{a}/{en_iyi} oranı referansa göre %{(en_kazanc - 1) * 100:.2f} arttı"
        return [Emir(a, 0, neden=neden), Emir(en_iyi, 1, agirlik=self.agirlik, neden=neden)]
