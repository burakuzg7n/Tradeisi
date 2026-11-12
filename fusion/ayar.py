"""Ayarlar: varsayilanlar + kokteki fuzyon_ayar.json (varsa) ustune yazar."""
from __future__ import annotations

import json
import os

from .veri import KOK

VARSAYILAN = {
    "semboller": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"],
    # Varsayilan 4 saatlik mum. Neden: gidis-donus maliyeti (~14 bps) 15 dakikalik mumda tipik
    # stop mesafesinin ~%35'ini yer (islem basi ~0,35R); 4 saatlikte ~%6'sini. Bu, sinyal
    # sonucuna bakilarak degil maliyet aritmetigiyle secildi. Degistirmek icin: --aralik 15m
    "aralik": "4h",
    "gecmis_gun": 1500,         # indirilecek gecmis (isinma + Q-ajan egitimi)
    "backtest_gun": 730,        # backtest'in degerlendirdigi son gun sayisi
    "canli_geri_gun": 30,       # canli kagit islem ilk acilista kac gun geriden oynatilarak baslar
    "baslangic_sermaye": 1000.0,  # her stratejinin kagit hesabi (USDT)
    "risk_yuzde": 1.0,          # stoplu islemlerde islem basi risk (ozsermaye %)
    "poz_tavan": 1.0,           # tek pozisyonun en buyuk nominali (ozsermaye kati)
    "max_kaldirac": 3.0,        # tum acik pozisyonlarin toplam nominali (ozsermaye kati)
    "max_pozisyon": 5,
    "short_acik": True,         # short = vadeli gibi kagit islem (fonlama modellenmez)
    "komisyon_bps": 5.0,        # her dolumda, nominal uzerinden
    "kayma_bps": 2.0,           # her dolumda, aleyhe
    "bekleme_bar": 8,           # stop sonrasi ayni sembolde bekleme
    "dd_siniri": 0.25,          # hesap bu dususe ulasinca kilitlenir
    "dd_kilit_gun": 7,          # kilit suresi (gun)
    "dd_kilit_bar": 0,          # >0 ise gun yerine dogrudan bar sayisi kullanilir
    "fuzyon_oy": 2,             # fuzyon oylamasinda gereken net oy
    "stratejiler": "hepsi",     # ya da ad listesi
    "takip": "hepsi",           # sinyali iletilecek strateji: "hepsi" | "lider" | strateji adi
    "webhook_url": "",          # sinyallerin POST edilecegi adres (bos = kapali)
    "panel_port": 8777,
    "cikti": "out/fusion",
}


def ayar_yolu() -> str:
    return os.path.join(KOK, "fuzyon_ayar.json")


def yukle(ustune: dict | None = None) -> dict:
    a = dict(VARSAYILAN)
    yol = ayar_yolu()
    if os.path.exists(yol):
        try:
            with open(yol, encoding="utf-8-sig") as f:
                kullanici = json.load(f)
            a.update({k: v for k, v in kullanici.items() if k in VARSAYILAN})
        except (OSError, ValueError) as e:
            print(f"UYARI: fuzyon_ayar.json okunamadi ({e}); varsayilanlar kullaniliyor.")
    if ustune:
        a.update(ustune)
    return a


def cikti_klasoru(a: dict) -> str:
    yol = a["cikti"] if os.path.isabs(a["cikti"]) else os.path.join(KOK, a["cikti"])
    os.makedirs(yol, exist_ok=True)
    return yol


def ornek_yaz() -> str:
    yol = ayar_yolu()
    if not os.path.exists(yol):
        with open(yol, "w", encoding="utf-8") as f:
            json.dump(VARSAYILAN, f, indent=2, ensure_ascii=False)
    return yol
