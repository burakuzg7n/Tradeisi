"""Komut satiri:  python -m fusion <komut>

  kontrol    Kurulum ve veri durumu
  veri       Binance'ten mum verisini indir / tamamla (anahtar gerekmez)
  backtest   Son N gunu tum stratejilerle oynat, tabloyu yaz   [--gun N] [--panel]
  canli      Canli KAGIT islem + panel (gercek emir yok)        [--bir-kez] [--sifirla] [--panelsiz]
  panel      Yalniz web panelini ac
  durum      Son canli/backtest tablosunu yazdir
  demo       Internetsiz deneme (sentetik veri) + panel
  kural      Metinden yeni strateji ekle:
             python -m fusion kural AD "long giris" ["long cikis" ["short giris" ["short cikis"]]]
  ayar       Duzenlenebilir fuzyon_ayar.json dosyasini olustur
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

from . import ayar as ayar_m
from . import canli, durum, panel, stratejiler, veri
from .kural import KuralHatasi, kural_kaydet
from .motor import Motor


def _ilerleme(sembol, imlec, son):
    print(f"\r  {sembol}: {time.strftime('%Y-%m-%d', time.gmtime(imlec / 1000))}", end="", flush=True)


def k_veri(a, args) -> int:
    print(f"Veri indiriliyor: {', '.join(a['semboller'])} · {a['aralik']} · {a['gecmis_gun']} gün")
    hata = 0
    for s in a["semboller"]:
        try:
            b = veri.guncelle(s, a["aralik"], a["gecmis_gun"], ilerleme=_ilerleme)
            print(f"\r  {s}: {len(b)} mum" + (f" ({durum._zaman(int(b.ts[0]))} → {durum._zaman(int(b.ts[-1]))})"
                                                if len(b) else " — VERİ YOK"))
        except ConnectionError as e:
            hata += 1
            print(f"\r  {s}: HATA — {e}")
    if hata:
        print("Bazı semboller indirilemedi. İnternet bağlantısını kontrol edip tekrar deneyin.")
    return 1 if hata == len(a["semboller"]) else 0


def _backtest(a, piyasa, mod: str, not_: str = ""):
    gun = int(a["backtest_gun"])
    k_bas = piyasa.k_bul(int(piyasa.T[-1]) - gun * 86_400_000)
    t0 = time.time()
    sonuc = Motor(piyasa, stratejiler.hepsi(a), a).kos(k_bas)
    d = durum.olustur(sonuc, mod, not_)
    durum.yaz(d, a, "backtest")
    y1, y2 = durum.islemleri_yaz(sonuc, a, "backtest"), durum.egrileri_yaz(sonuc, a, "backtest")
    print(f"{d['bar_sayisi']} bar · {durum._zaman(d['bas_ts'])} → {durum._zaman(d['son_ts'])} · "
          f"{time.time() - t0:.1f} sn")
    durum.tablo_yazdir(d)
    print(f"İşlem listesi : {y1}\nÖzsermaye     : {y2}")
    return d


def k_backtest(a, args) -> int:
    if args.gun:
        a["backtest_gun"] = args.gun
    piyasa = veri.piyasa_yukle(a["semboller"], a["aralik"])
    eksik = [s for s in a["semboller"] if s not in piyasa.barlar]
    if eksik:
        print(f"UYARI: verisi olmayan semboller atlandı: {', '.join(eksik)}")
    _backtest(a, piyasa, "backtest")
    if args.panel:
        panel.baslat(a)
    return 0


def k_demo(a, args) -> int:
    print("DEMO: sentetik (uydurma) veriyle çalışıyor — yalnız programı denemek içindir.")
    a["backtest_gun"] = 60
    piyasa = veri.piyasa_yukle(a["semboller"], a["aralik"], sentetik_mi=True, sentetik_n=12_000)
    _backtest(a, piyasa, "demo", "Sentetik veri: sonuçların piyasa anlamı yoktur")
    if not args.panelsiz:
        panel.baslat(a)
    return 0


def k_canli(a, args) -> int:
    if args.sifirla:
        canli.sifirla(a)
        print("Canlı kâğıt hesaplar sıfırlandı.")
    sunucu = None
    if not args.panelsiz and not args.bir_kez:
        sunucu = panel.baslat(a, arka_plan=True)
    try:
        canli.dongu(a, bir_kez=args.bir_kez)
    except KeyboardInterrupt:
        print("\nDurduruldu. Yeniden başlattığınızda kaldığı yerden devam eder.")
    finally:
        if sunucu:
            sunucu.shutdown()
    return 0


def k_panel(a, args) -> int:
    panel.baslat(a)
    return 0


def k_durum(a, args) -> int:
    bulundu = False
    for ad in ("canli", "backtest"):
        yol = os.path.join(ayar_m.cikti_klasoru(a), f"durum_{ad}.json")
        if os.path.exists(yol):
            with open(yol, encoding="utf-8") as f:
                d = json.load(f)
            print(f"== {ad.upper()} · {durum._zaman(d['bas_ts'])} → {durum._zaman(d['son_ts'])}")
            durum.tablo_yazdir(d)
            bulundu = True
    if not bulundu:
        print("Henüz sonuç yok. Önce backtest ya da canlı çalıştırın.")
    return 0


def k_kontrol(a, args) -> int:
    import numpy
    print(f"Python {sys.version.split()[0]} · numpy {numpy.__version__} — tamam")
    for s in a["semboller"]:
        b = veri.csv_oku(veri.csv_yolu(s, a["aralik"]))
        print(f"  {s}_{a['aralik']}: " + (f"{len(b)} mum, son {durum._zaman(int(b.ts[-1]))}" if len(b) else "veri yok"))
    print(f"Stratejiler: {', '.join(s.ad for s in stratejiler.hepsi(a))}")
    return 0


def k_kural(a, args) -> int:
    try:
        yol = kural_kaydet(args.ad, args.long_giris, args.long_cikis, args.short_giris, args.short_cikis,
                           args.stop_atr, args.kar_atr)
    except KuralHatasi as e:
        print(f"Kural kabul edilmedi: {e}")
        return 1
    print(f"Kural stratejisi eklendi: {yol}\nBir sonraki backtest/canlı çalıştırmada arenaya katılır.")
    return 0


def k_ayar(a, args) -> int:
    print(f"Ayar dosyası: {ayar_m.ornek_yaz()} (Not Defteri ile düzenleyebilirsiniz)")
    return 0


def main(argv=None) -> int:
    for akis in (sys.stdout, sys.stderr):
        try:
            akis.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    p = argparse.ArgumentParser(prog="python -m fusion", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    alt = p.add_subparsers(dest="komut")
    alt.add_parser("kontrol")
    alt.add_parser("veri")
    b = alt.add_parser("backtest")
    b.add_argument("--gun", type=int, default=0)
    b.add_argument("--panel", action="store_true")
    c = alt.add_parser("canli")
    c.add_argument("--bir-kez", action="store_true")
    c.add_argument("--sifirla", action="store_true")
    c.add_argument("--panelsiz", action="store_true")
    alt.add_parser("panel")
    alt.add_parser("durum")
    d = alt.add_parser("demo")
    d.add_argument("--panelsiz", action="store_true")
    k = alt.add_parser("kural")
    k.add_argument("ad")
    k.add_argument("long_giris")
    k.add_argument("long_cikis", nargs="?", default="")
    k.add_argument("short_giris", nargs="?", default="")
    k.add_argument("short_cikis", nargs="?", default="")
    k.add_argument("--stop-atr", type=float, default=2.0)
    k.add_argument("--kar-atr", type=float, default=0.0)
    alt.add_parser("ayar")
    args = p.parse_args(argv)
    if not args.komut:
        p.print_help()
        return 0
    a = ayar_m.yukle()
    try:
        return globals()["k_" + args.komut](a, args)
    except ValueError as e:
        print(f"HATA: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
