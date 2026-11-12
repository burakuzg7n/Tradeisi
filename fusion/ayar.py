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
    "canli_max_bar": 60_000,    # canli oturum bu kadar mumu asinca yeni sezon baslar (hiz icin)
    "panel_port": 8777,
    "cikti": "out/fusion",
    "veri": "data",             # mum verisi klasoru (kok klasore gore)
}


# Araliga bagli on ayarlar (gun). Hedef: ~35-48 bin mumluk gecmis, bunun ~22 bini isinma/egitim.
ON_AYAR = {
    "1m":  {"gecmis_gun": 30,   "backtest_gun": 10,   "canli_geri_gun": 1,   "dd_kilit_gun": 1},
    "3m":  {"gecmis_gun": 75,   "backtest_gun": 25,   "canli_geri_gun": 2,   "dd_kilit_gun": 1},
    "5m":  {"gecmis_gun": 150,  "backtest_gun": 60,   "canli_geri_gun": 3,   "dd_kilit_gun": 1},
    "10m": {"gecmis_gun": 300,  "backtest_gun": 120,  "canli_geri_gun": 5,   "dd_kilit_gun": 2},
    "15m": {"gecmis_gun": 500,  "backtest_gun": 240,  "canli_geri_gun": 7,   "dd_kilit_gun": 2},
    "30m": {"gecmis_gun": 800,  "backtest_gun": 365,  "canli_geri_gun": 14,  "dd_kilit_gun": 3},
    "1h":  {"gecmis_gun": 1500, "backtest_gun": 600,  "canli_geri_gun": 21,  "dd_kilit_gun": 5},
    "2h":  {"gecmis_gun": 1500, "backtest_gun": 730,  "canli_geri_gun": 30,  "dd_kilit_gun": 7},
    "4h":  {"gecmis_gun": 1500, "backtest_gun": 730,  "canli_geri_gun": 30,  "dd_kilit_gun": 7},
    "1d":  {"gecmis_gun": 3000, "backtest_gun": 1500, "canli_geri_gun": 120, "dd_kilit_gun": 14},
}
ARALIGA_BAGLI = ("gecmis_gun", "backtest_gun", "canli_geri_gun", "dd_kilit_gun")


def aralik_uygula(a: dict, aralik: str) -> dict:
    """Araligi degistirir ve kullanicinin ayar dosyasinda ELLE yazmadigi gun ayarlarini
    o araligin on ayarina ceker."""
    if aralik not in ON_AYAR:
        raise ValueError(f"Bilinmeyen aralik: {aralik}. Secenekler: {', '.join(ON_AYAR)}")
    a["aralik"] = aralik
    for k, v in ON_AYAR[aralik].items():
        if k not in a.get("_sabit", ()):
            a[k] = v
    return a


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
            # Elle yazilmis sayilmasi icin varsayilandan FARKLI olmali (eski surumun urettigi
            # ornek dosya bu anahtarlari varsayilan degerleriyle iceriyordu).
            a["_sabit"] = [k for k in ARALIGA_BAGLI
                           if k in kullanici and kullanici[k] != VARSAYILAN[k]]
        except (OSError, ValueError) as e:
            print(f"UYARI: fuzyon_ayar.json okunamadi ({e}); varsayilanlar kullaniliyor.")
    try:
        aralik_uygula(a, a["aralik"])
    except ValueError as e:
        print(f"UYARI: {e} 4h kullaniliyor.")
        aralik_uygula(a, "4h")
    if ustune:
        a.update(ustune)
    return a


def aralik_kaydet(aralik: str) -> str:
    """Secilen araligi fuzyon_ayar.json'a yazar (dosyadaki diger ayarlara dokunmaz)."""
    if aralik not in ON_AYAR:
        raise ValueError(f"Bilinmeyen aralik: {aralik}. Secenekler: {', '.join(ON_AYAR)}")
    yol = ayar_yolu()
    icerik = {}
    if os.path.exists(yol):
        try:
            with open(yol, encoding="utf-8-sig") as f:
                icerik = json.load(f)
        except (OSError, ValueError):
            icerik = {}
    icerik["aralik"] = aralik
    with open(yol, "w", encoding="utf-8") as f:
        json.dump(icerik, f, indent=2, ensure_ascii=False)
    return yol


def cikti_klasoru(a: dict) -> str:
    yol = a["cikti"] if os.path.isabs(a["cikti"]) else os.path.join(KOK, a["cikti"])
    os.makedirs(yol, exist_ok=True)
    return yol


def veri_klasoru(a: dict) -> str:
    yol = a.get("veri") or "data"
    yol = yol if os.path.isabs(yol) else os.path.join(KOK, yol)
    os.makedirs(yol, exist_ok=True)
    return yol


def ornek_yaz() -> str:
    yol = ayar_yolu()
    if not os.path.exists(yol):
        with open(yol, "w", encoding="utf-8") as f:   # gun ayarlari araliga gore otomatik secilir
            json.dump({k: v for k, v in VARSAYILAN.items() if k not in ARALIGA_BAGLI}, f, indent=2,
                      ensure_ascii=False)
    return yol
