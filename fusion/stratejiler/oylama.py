"""Fuzyon oylamasi: diger tum stratejilerin o anki yonunu oy sayar (AI-Trader arenasindaki
ajanlarin ortak aklini tek hesapta toplama fikri). Listede EN SONDA calisir."""
from ..motor import Emir
from ..strateji import Strateji


class FuzyonOylama(Strateji):
    ad = "fuzyon"
    baslik = "Füzyon: diğer stratejilerin çoğunluk oyu"
    kaynak = "HKUDS/AI-Trader (arena) + hepsi"
    stop_atr = 2.5

    def oylar(self, sembol, b):
        arti, eksi = [], []
        for ad, h in b.hesaplar.items():
            if ad == self.ad:
                continue
            n = h.niyet(sembol)
            if n > 0:
                arti.append(ad)
            elif n < 0:
                eksi.append(ad)
        return arti, eksi

    def bar(self, k, hesap, b):
        esik = int(b.ayar["fuzyon_oy"])
        emirler = []
        for s in b.piyasa.semboller:
            i = b.idx[s][k]
            if i < 0:
                continue
            atr = b.atr[s][i]
            if atr != atr or atr <= 0:
                continue
            arti, eksi = self.oylar(s, b)
            net = len(arti) - len(eksi)
            n = hesap.niyet(s)
            neden = f"oylar: long {len(arti)} ({', '.join(arti) or '-'}) / short {len(eksi)} ({', '.join(eksi) or '-'})"
            if n == 0:
                if net >= esik:
                    emirler.append(Emir(s, 1, stop_mesafe=self.stop_atr * atr, neden=neden))
                elif net <= -esik and b.ayar["short_acik"]:
                    emirler.append(Emir(s, -1, stop_mesafe=self.stop_atr * atr, neden=neden))
            elif (n > 0 and net <= 0) or (n < 0 and net >= 0):
                emirler.append(Emir(s, 0, neden="çoğunluk bozuldu; " + neden))
        return emirler
