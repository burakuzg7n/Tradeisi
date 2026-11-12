"""Canli kagit islem dongusu.

Her yeni kapanan mumda: veriyi tamamla -> baslangic anindan bugune TUM barlari ayni motorla
yeniden oynat -> yeni sinyalleri ilet -> panel dosyasini yaz. Kalici durum yalniz baslangic
zamani ve son iletilen sinyal zamanidir; program kapanip acilsa da ayni sonucu uretir.
"""
from __future__ import annotations

import json
import os
import time

from . import durum, iletim, stratejiler, veri
from .ayar import cikti_klasoru, veri_klasoru
from .motor import Motor


def _kayit_yolu(a: dict) -> str:
    return os.path.join(cikti_klasoru(a), "canli.json")


def kayit_oku(a: dict) -> dict:
    try:
        with open(_kayit_yolu(a), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def kayit_yaz(a: dict, k: dict) -> None:
    gecici = _kayit_yolu(a) + ".tmp"
    with open(gecici, "w", encoding="utf-8") as f:
        json.dump(k, f)
    veri.degistir(gecici, _kayit_yolu(a))


def tur(a: dict, simdi_ms: int | None = None, indir: bool = True, piyasa=None, sessiz: bool = False):
    """Tek dongu adimi. (durum_sozlugu, iletilen_sinyal_sayisi) dondurur."""
    uyari = ""
    if piyasa is None:
        if indir:
            uyari = veri.hepsini_guncelle(a["semboller"], a["aralik"], a["gecmis_gun"],
                                          veri_klasoru(a))
            if uyari and not sessiz:
                print("  UYARI: " + uyari)
        piyasa = veri.piyasa_yukle(a["semboller"], a["aralik"], veri_klasoru(a))
    simdi_ms = simdi_ms or veri.simdi_ms()
    k = kayit_oku(a)
    if k and (k.get("aralik") != a["aralik"] or k.get("semboller") != list(a["semboller"])):
        if not sessiz:
            print("  Aralık ya da sembol listesi değişmiş: canlı kâğıt hesaplar baştan başlatılıyor.")
        sifirla(a)
        k = {}
    if "baslangic_ts" not in k:
        k = {"baslangic_ts": int(piyasa.T[-1]) - int(a["canli_geri_gun"]) * 86_400_000,
             "son_iletilen_ts": int(piyasa.T[-1]) + piyasa.adim_ms, "ilk_acilis": simdi_ms,
             "aralik": a["aralik"], "semboller": list(a["semboller"])}
        kayit_yaz(a, k)
    piyasa = veri.kirp(piyasa, k["baslangic_ts"])
    sonuc = Motor(piyasa, stratejiler.hepsi(a), a).kos(piyasa.k_bul(k["baslangic_ts"]))
    d = durum.olustur(sonuc, "canli", uyari)
    lider = d["tablo"][0]["ad"] if d["tablo"] else None
    taze = simdi_ms - 2 * piyasa.adim_ms        # kesinti sonrasi eski sinyalleri yagdirma
    yeni = [o for o in sonuc.olaylar if o["ts"] > k["son_iletilen_ts"]]
    gonder = [o for o in iletim.sec(yeni, a.get("takip"), lider) if o["ts"] >= taze]
    n = iletim.ilet(gonder, a, sessiz)
    if yeni:
        k["son_iletilen_ts"] = max(o["ts"] for o in yeni)
        kayit_yaz(a, k)
    durum.yaz(d, a, "canli")
    return d, n


def sifirla(a: dict) -> None:
    for ad in ("canli.json", "durum_canli.json"):
        yol = os.path.join(cikti_klasoru(a), ad)
        if os.path.exists(yol):
            veri.degistir(yol, yol + ".eski")


def dongu(a: dict, bir_kez: bool = False) -> None:
    adim = veri.ARALIK_MS[a["aralik"]]
    print(f"Canlı KÂĞIT işlem başladı ({a['aralik']}, {len(a['semboller'])} sembol). "
          f"Gerçek emir gönderilmez. Durdurmak için Ctrl+C.")
    while True:
        try:
            d, n = tur(a)
            en = d["tablo"][0] if d["tablo"] else None
            print(time.strftime("%H:%M:%S") + f"  {d['bar_sayisi']} bar oynatıldı, {n} yeni sinyal"
                  + (f", lider: {en['ad']} ({en['ozsermaye']:.2f})" if en else ""))
        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(time.strftime("%H:%M:%S") + f"  HATA: {type(e).__name__}: {e} — 60 sn sonra yeniden denenecek")
            if bir_kez:
                raise
            time.sleep(60)
            continue
        if bir_kez:
            return
        simdi = veri.simdi_ms()                       # Binance saatine gore
        sonraki = (simdi // adim + 1) * adim + 5000   # mum kapanisindan 5 sn sonra
        time.sleep(max(5.0, (sonraki - simdi) / 1000.0))
