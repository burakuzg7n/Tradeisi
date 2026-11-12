"""Canli kagit islem dongusu.

Acilista: baslangic anindan bugune kadar olan mumlar ayni motorla yeniden oynatilir (kalici
durum yalniz baslangic zamani ve son iletilen sinyal zamanidir; program kapanip acilsa da ayni
sonuc uretilir). Sonraki her yeni mumda yalniz o mum islenir — 1 dakikalik mumda da dongu
saniyeler icinde biter. Gecmis verinin islenmis kismi degismisse (gec gelen mum vb.) oturum
guvenli tarafta kalip bastan oynatilir.
"""
from __future__ import annotations

import json
import os
import time

from . import durum, iletim, stratejiler, veri
from .ayar import cikti_klasoru, veri_klasoru
from .motor import Motor

_OTURUM: dict = {}     # kayit yolu -> {"motor", "imza", "n", "sayim"}


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


def _yeni_kayit(a: dict, piyasa, simdi_ms: int, sezon: int = 1) -> dict:
    return {"baslangic_ts": int(piyasa.T[-1]) - int(a["canli_geri_gun"]) * 86_400_000,
            "son_iletilen_ts": int(piyasa.T[-1]) + piyasa.adim_ms, "ilk_acilis": simdi_ms,
            "aralik": a["aralik"], "semboller": list(a["semboller"]), "sezon": sezon}


def _sayim(piyasa, n: int) -> dict:
    return {s: int((piyasa.idx[s][:n] >= 0).sum()) for s in piyasa.semboller}


def _devam_edilebilir(o: dict, piyasa, imza: str) -> bool:
    """Onceki turda islenen kisim aynen duruyor mu (yalniz sona mum eklenmis mi)?"""
    n = o["n"]
    return (o["imza"] == imza and len(piyasa.T) >= n and int(piyasa.T[0]) == o["ilk"]
            and int(piyasa.T[n - 1]) == o["son"] and _sayim(piyasa, n) == o["sayim"])


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
    yol = _kayit_yolu(a)
    k = kayit_oku(a)
    if k and (k.get("aralik") != a["aralik"] or k.get("semboller") != list(a["semboller"])):
        if not sessiz:
            print("  Aralık ya da sembol listesi değişmiş: canlı kâğıt hesaplar baştan başlatılıyor.")
        sifirla(a)
        k = {}
    if "baslangic_ts" not in k:
        k = _yeni_kayit(a, piyasa, simdi_ms)
        kayit_yaz(a, k)
    ham = piyasa
    piyasa = veri.kirp(ham, k["baslangic_ts"])
    if len(piyasa.T) - piyasa.k_bul(k["baslangic_ts"]) > int(a["canli_max_bar"]):
        # Sezon siniri: oturum cok uzadi. Son tablo arsivlenir, hesaplar bastan baslar.
        eski = os.path.join(cikti_klasoru(a), "durum_canli.json")
        if os.path.exists(eski):
            veri.degistir(eski, os.path.join(cikti_klasoru(a), f"sezon_{k.get('sezon', 1):03d}.json"))
        k = _yeni_kayit(a, ham, simdi_ms, int(k.get("sezon", 1)) + 1)
        kayit_yaz(a, k)
        _OTURUM.pop(yol, None)
        piyasa = veri.kirp(ham, k["baslangic_ts"])
        if not sessiz:
            print(f"  Yeni sezon başladı ({k['sezon']}); önceki tablo arşivlendi.")
    imza = json.dumps({x: y for x, y in a.items() if not x.startswith("_")}, sort_keys=True,
                      default=str) + str(k["baslangic_ts"])
    o = _OTURUM.get(yol)
    if o is not None and _devam_edilebilir(o, piyasa, imza):
        motor = o["motor"]
        if len(piyasa.T) > o["n"]:
            motor.piyasa_degistir(piyasa)
    else:
        motor = Motor(piyasa, stratejiler.hepsi(a), a)
        motor.baslat(piyasa.k_bul(k["baslangic_ts"]))
    sonuc = motor.ilerle()
    n = len(piyasa.T)
    _OTURUM[yol] = {"motor": motor, "imza": imza, "n": n, "ilk": int(piyasa.T[0]),
                    "son": int(piyasa.T[n - 1]), "sayim": _sayim(piyasa, n)}
    d = durum.olustur(sonuc, "canli", uyari)
    d["sezon"] = int(k.get("sezon", 1))
    lider = d["tablo"][0]["ad"] if d["tablo"] else None
    taze = simdi_ms - 2 * piyasa.adim_ms        # kesinti sonrasi eski sinyalleri yagdirma
    yeni = [e for e in sonuc.olaylar if e["ts"] > k["son_iletilen_ts"]]
    gonder = [e for e in iletim.sec(yeni, a.get("takip"), lider) if e["ts"] >= taze]
    adet = iletim.ilet(gonder, a, sessiz)
    if yeni:
        k["son_iletilen_ts"] = max(e["ts"] for e in yeni)
        kayit_yaz(a, k)
    durum.yaz(d, a, "canli")
    return d, adet


def sifirla(a: dict) -> None:
    _OTURUM.pop(_kayit_yolu(a), None)
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
            t0 = time.time()
            d, n = tur(a)
            en = d["tablo"][0] if d["tablo"] else None
            print(time.strftime("%H:%M:%S") + f"  {d['bar_sayisi']} mum, {n} yeni sinyal"
                  + (f", lider: {en['ad']} ({en['ozsermaye']:.2f})" if en else "")
                  + f"  [{time.time() - t0:.1f} sn]")
        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(time.strftime("%H:%M:%S") + f"  HATA: {type(e).__name__}: {e} — yeniden denenecek")
            if bir_kez:
                raise
            _OTURUM.pop(_kayit_yolu(a), None)       # yarim kalmis oturumu birak, bastan oynat
            time.sleep(min(60.0, adim / 2000.0))
            continue
        if bir_kez:
            return
        simdi = veri.simdi_ms()                       # Binance saatine gore
        sonraki = (simdi // adim + 1) * adim + 5000   # mum kapanisindan 5 sn sonra
        time.sleep(max(2.0, (sonraki - simdi) / 1000.0))
