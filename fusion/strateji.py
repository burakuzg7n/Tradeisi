"""Strateji arayuzu (freqtrade'in 'gostergeleri doldur -> giris/cikis sinyali' duzeninden esinli)."""
from __future__ import annotations

import numpy as np

from .motor import Emir


class Strateji:
    ad = "strateji"
    baslik = ""
    kaynak = ""      # ilham alinan proje
    oy_verir = True  # fuzyon oylamasinda yon gorusu sayilir mi

    def sifirla(self) -> None:
        """Islem durumunu (strateji hafizasini) sifirla. Oturum basinda bir kez cagrilir."""

    def hazirla(self, piyasa, k_bas: int, ayar: dict) -> None:
        """Tum gecmis uzerinde nedensel gostergeleri hesapla. k_bas: degerlendirmenin ilk adimi.
        Canli modda her yeni mumda YENIDEN cagrilir: islem durumunu burada sifirlama."""

    def bar(self, k: int, hesap, b) -> list:
        """k barinin KAPANISINDA cagrilir; emirler k+1 acilisinda dolar."""
        return []


class DiziStrateji(Strateji):
    """Sinyalleri bool dizileri olarak ureten stratejiler icin ortak govde.

    diziler() -> {"le": long giris, "lx": long cikis, "se": short giris, "sx": short cikis,
                  "carpan": (istege bagli) risk olcegi dizisi}
    """
    stop_atr = 2.0
    kar_atr = 0.0

    def diziler(self, sembol: str, bars, piyasa) -> dict:
        raise NotImplementedError

    def neden(self, sembol: str, i: int, yon: int) -> str:
        return self.baslik

    def hazirla(self, piyasa, k_bas, ayar):
        self._d = {}
        for s in piyasa.semboller:
            d = self.diziler(s, piyasa.barlar[s], piyasa)
            n = len(piyasa.barlar[s])
            hazir = {}
            for anahtar in ("le", "lx", "se", "sx"):
                dizi = d.get(anahtar)
                hazir[anahtar] = (np.zeros(n, dtype=bool) if dizi is None
                                  else np.asarray(dizi, dtype=bool)).tolist()
            carpan = d.get("carpan")
            hazir["carpan"] = None if carpan is None else np.nan_to_num(carpan, nan=1.0).tolist()
            self._d[s] = hazir

    def _emir(self, s: str, i: int, yon: int, atr: float) -> Emir:
        d = self._d[s]
        return Emir(s, yon, stop_mesafe=self.stop_atr * atr if self.stop_atr else None,
                    kar_mesafe=self.kar_atr * atr if self.kar_atr else None,
                    carpan=d["carpan"][i] if d["carpan"] else 1.0, neden=self.neden(s, i, yon))

    def bar(self, k, hesap, b):
        emirler = []
        short_ok = b.ayar["short_acik"]
        for s in b.piyasa.semboller:
            i = b.idx[s][k]
            if i < 0:
                continue
            atr = b.atr[s][i]
            if atr != atr or atr <= 0:
                continue
            d = self._d[s]
            n = hesap.niyet(s)
            if n == 0:
                if d["le"][i]:
                    emirler.append(self._emir(s, i, 1, atr))
                elif d["se"][i] and short_ok:
                    emirler.append(self._emir(s, i, -1, atr))
            elif n > 0:
                if d["se"][i] and short_ok:
                    emirler.append(self._emir(s, i, -1, atr))
                elif d["lx"][i]:
                    emirler.append(Emir(s, 0, neden="cikis kurali"))
            else:
                if d["le"][i]:
                    emirler.append(self._emir(s, i, 1, atr))
                elif d["sx"][i]:
                    emirler.append(Emir(s, 0, neden="cikis kurali"))
        return emirler
