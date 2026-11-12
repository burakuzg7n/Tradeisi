"""Komut satiri ve servisin ortak kullandigi isler."""
from __future__ import annotations

import time

from . import durum, stratejiler, veri
from .ayar import veri_klasoru
from .motor import Motor


def backtest(a: dict, piyasa=None, mod: str = "backtest", not_: str = "") -> tuple:
    """a['backtest_gun'] gunluk donemi tum stratejilerle oynatir, cikti dosyalarini yazar.
    (durum_sozlugu, sure_sn, eksik_semboller) dondurur."""
    if piyasa is None:
        piyasa = veri.piyasa_yukle(a["semboller"], a["aralik"], veri_klasoru(a))
    eksik = [s for s in a["semboller"] if s not in piyasa.barlar]
    bas_ts = int(piyasa.T[-1]) - int(a["backtest_gun"]) * 86_400_000
    piyasa = veri.kirp(piyasa, bas_ts)
    t0 = time.time()
    sonuc = Motor(piyasa, stratejiler.hepsi(a), a).kos(piyasa.k_bul(bas_ts))
    d = durum.olustur(sonuc, mod, not_)
    durum.yaz(d, a, "backtest")
    durum.islemleri_yaz(sonuc, a, "backtest")
    durum.egrileri_yaz(sonuc, a, "backtest")
    return d, time.time() - t0, eksik
